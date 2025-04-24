"""User Account Controllers."""

from __future__ import annotations

import uuid
from typing import TYPE_CHECKING

from advanced_alchemy.utils.text import slugify
from litestar import Controller, Request, Response, get, post
from litestar.di import Provide
from litestar.params import Parameter

from app.domain.accounts import urls
from app.domain.accounts.deps import provide_users_service
from app.domain.accounts.guards import auth, requires_active_user
from app.domain.accounts.schemas import (
    AccountRegisterMagicLink,
    User,
)
from app.domain.accounts.services import RoleService
from app.lib.deps import create_service_provider

if TYPE_CHECKING:
    from litestar.security.jwt import OAuth2Login

    from app.db import models as m
    from app.domain.accounts.services import UserService


class AccessController(Controller):
    """User login and registration."""

    tags = ["Access"]
    dependencies = {
        "users_service": Provide(provide_users_service),
        "roles_service": Provide(create_service_provider(RoleService)),
    }

    @get(operation_id="AccountLogin", path=urls.ACCOUNT_LOGIN, exclude_from_auth=True)
    async def login(
        self, users_service: UserService, username: str, token: str
    ) -> Response[OAuth2Login]:
        """Authenticate a user using a magic link."""
        user = await users_service.authenticate_magic_token(username, token)
        return auth.login(user.email)

    @post(
        operation_id="AccountLogout", path=urls.ACCOUNT_LOGOUT, exclude_from_auth=True
    )
    async def logout(self, request: Request) -> Response:
        """Account Logout"""
        request.cookies.pop(auth.key, None)
        request.clear_session()

        response = Response(
            {"message": "OK"},
            status_code=200,
        )
        response.delete_cookie(auth.key)

        return response

    @post(
        operation_id="AccountRegisterMagicLink",
        path=urls.ACCOUNT_REGISTER_MAGIC_LINK,
    )
    async def signup_magic_link(
        self,
        request: Request,
        users_service: UserService,
        roles_service: RoleService,
        data: AccountRegisterMagicLink,
    ) -> User:
        """User Signup."""
        user_data = data.to_dict()
        role_obj = await roles_service.get_one_or_none(
            slug=slugify(users_service.default_role)
        )
        if role_obj is not None:
            user_data.update({"role_id": role_obj.id})

        token = str(uuid.uuid4())
        user_data.update({"magic_link_token": token})
        user = await users_service.create(user_data)

        new_user = await users_service.get_one_or_none(id=user.id)

        request.app.emit(
            event_id="send_magic_link_email",
            user=user,
            token=token,
        )
        return users_service.to_schema(new_user, schema_type=User)

    @get(
        operation_id="GetUser",
        path=urls.USER_DETAIL,
        guards=[requires_active_user],
    )
    async def get_user(
        self,
        users_service: UserService,
        user_id: uuid.UUID = Parameter(
            title="User ID", description="The user to retrieve."
        ),
    ) -> User:
        """Get an user."""

        user = await users_service.get(user_id)
        return users_service.to_schema(user, schema_type=User)

    @get(
        operation_id="AccountProfile",
        path=urls.ACCOUNT_PROFILE,
        guards=[requires_active_user],
    )
    async def profile(self, current_user: m.User, users_service: UserService) -> User:
        """User Profile."""
        return users_service.to_schema(current_user, schema_type=User)
