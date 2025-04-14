"""User Account Controllers."""

from __future__ import annotations

from typing import Annotated

from app.domain.accounts import urls
from app.domain.accounts.deps import provide_users_service

# from app.domain.accounts.guards import auth
from app.domain.accounts.schemas import AccountLogin
from app.domain.accounts.services import UserService
from litestar import Controller, Request, get, post
from litestar.di import Provide
from litestar.enums import RequestEncodingType
from litestar.params import Body


class AccessController(Controller):
    """User login and registration."""

    tags = ["Access"]
    dependencies = {
        "users_service": Provide(provide_users_service),
    }

    @get("/session", sync_to_thread=False)
    def check_session_handler(self, request: Request) -> dict[str, bool]:
        """Handler function that accesses request.session."""
        return {"has_session": request.session != {}}

    @post("/session", sync_to_thread=False, exclude_from_auth=True)
    def create_session_handler(self, request: Request) -> None:
        """Handler to set the session."""
        if not request.session:
            print("-> Setting session")
            # value can be a dictionary or pydantic model
            request.set_session({"username": "moishezuchmir"})
            print(request.session)

    @post(operation_id="AccountLogin", path=urls.ACCOUNT_LOGIN, exclude_from_auth=True)
    async def login(
        self,
        users_service: UserService,
        data: Annotated[
            AccountLogin,
            Body(title="Token Login", media_type=RequestEncodingType.URL_ENCODED),
        ],
    ) -> None:
        """Authenticate a user."""
        # user = await users_service.authenticate(data.username, data.password)
        # return auth.login(user.email)
