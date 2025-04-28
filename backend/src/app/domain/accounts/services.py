from __future__ import annotations

from datetime import UTC, datetime, timedelta, timezone
from typing import Any
from uuid import UUID  # noqa: TC003

from advanced_alchemy.repository import (
    SQLAlchemyAsyncRepository,
    SQLAlchemyAsyncSlugRepository,
)
from advanced_alchemy.service import (
    ModelDictT,
    SQLAlchemyAsyncRepositoryService,
    is_dict,
    is_dict_with_field,
    is_dict_without_field,
    schema_dump,
)
from litestar.exceptions import PermissionDeniedException

from app.config import constants
from app.db import models as m
from app.lib import crypt


class UserRepository(SQLAlchemyAsyncRepository[m.User]):
    """User SQLAlchemy Repository."""

    model_type = m.User


class UserService(SQLAlchemyAsyncRepositoryService[m.User]):
    """Handles database operations for users."""

    repository_type = UserRepository
    default_role = constants.DEFAULT_USER_ROLE
    match_fields = ["email"]

    async def to_model_on_create(self, data: ModelDictT[m.User]) -> ModelDictT[m.User]:
        return await self._populate_model(data)

    async def to_model_on_update(self, data: ModelDictT[m.User]) -> ModelDictT[m.User]:
        return await self._populate_model(data)

    async def to_model_on_upsert(self, data: ModelDictT[m.User]) -> ModelDictT[m.User]:
        return await self._populate_model(data)

    async def authenticate_magic_token(
        self, username: str, password: bytes | str
    ) -> m.User:
        """Authenticate a user against the stored hashed magic link token."""
        from app.config import get_settings

        settings = get_settings()

        db_obj = await self.get_one_or_none(email=username)

        if db_obj is None:
            msg = "User not found or password invalid"
            raise PermissionDeniedException(detail=msg)

        await self._check_permissions(db_obj, password, db_obj.magic_link_hashed_token)

        now = datetime.now(timezone.utc)

        if db_obj.magic_link_sent_at and (
            db_obj.magic_link_sent_at
            + timedelta(seconds=settings.email.MAGIC_LINK_DURATION)
            < now
        ):
            msg = "Magic link token expired"
            raise PermissionDeniedException(detail=msg)

        db_obj.magic_link_hashed_token = None
        db_obj.magic_link_sent_at = None

        await self.repository.update(db_obj)

        return db_obj

    async def authenticate(self, username: str, password: bytes | str) -> m.User:
        """Authenticate a user against the stored hashed password."""
        db_obj = await self.get_one_or_none(email=username)

        if db_obj is None:
            msg = "User not found or password invalid"
            raise PermissionDeniedException(detail=msg)

        await self._check_permissions(db_obj, password, db_obj.hashed_password)

        return db_obj

    async def _check_permissions(
        self, db_obj: m.User | None, password: str, hashed_password: str
    ) -> None:
        if hashed_password is None:
            msg = "User not found or password invalid"
            raise PermissionDeniedException(detail=msg)
        if not await crypt.verify_password(password, hashed_password):
            msg = "User not found or password invalid"
            raise PermissionDeniedException(detail=msg)
        if not db_obj.is_active:
            msg = "User account is inactive"
            raise PermissionDeniedException(detail=msg)

    async def update_password(self, data: dict[str, Any], db_obj: m.User) -> None:
        """Modify stored user password."""
        if db_obj.hashed_password is None:
            msg = "User not found or password invalid"
            raise PermissionDeniedException(detail=msg)
        if not await crypt.verify_password(
            data["current_password"], db_obj.hashed_password
        ):
            msg = "User not found or password invalid"
            raise PermissionDeniedException(detail=msg)
        if not db_obj.is_active:
            msg = "User account is not active"
            raise PermissionDeniedException(detail=msg)
        db_obj.hashed_password = await crypt.get_password_hash(data["new_password"])
        await self.repository.update(db_obj)

    @staticmethod
    async def has_role_id(db_obj: m.User, role_id: UUID) -> bool:
        """Return true if user has specified role ID"""
        return any(
            assigned_role.role_id
            for assigned_role in db_obj.roles
            if assigned_role.role_id == role_id
        )

    @staticmethod
    async def has_role(db_obj: m.User, role_name: str) -> bool:
        """Return true if user has specified role ID"""
        return any(
            assigned_role.role_id
            for assigned_role in db_obj.roles
            if assigned_role.role_name == role_name
        )

    @staticmethod
    def is_superuser(user: m.User) -> bool:
        return bool(
            user.is_superuser
            or any(
                assigned_role.role.name
                for assigned_role in user.roles
                if assigned_role.role.name in {"Superuser"}
            ),
        )

    async def _populate_model(self, data: ModelDictT[m.User]) -> ModelDictT[m.User]:
        data = schema_dump(data)
        data = await self._populate_with_hashed_password(data)
        data = await self._populate_with_role_and_profile(data)
        return data

    async def _populate_with_hashed_password(
        self, data: ModelDictT[m.User]
    ) -> ModelDictT[m.User]:
        if (
            is_dict(data)
            and (magic_link_token := data.pop("magic_link_token", None)) is not None
        ):
            data["magic_link_hashed_token"] = await crypt.get_password_hash(
                magic_link_token
            )
        if is_dict(data) and (password := data.pop("password", None)) is not None:
            data["hashed_password"] = await crypt.get_password_hash(password)
        return data

    async def _populate_with_role_and_profile(
        self, data: ModelDictT[m.User]
    ) -> ModelDictT[m.User]:
        first_name = data.pop("first_name", None) if is_dict(data) else None
        last_name = data.pop("last_name", None) if is_dict(data) else None
        organization = data.pop("organization", None) if is_dict(data) else None
        role_id = data.pop("role_id", None) if is_dict(data) else None

        if is_dict(data):
            data = await self.to_model(data)

        if role_id is not None:
            data.roles.append(
                m.UserRole(role_id=role_id, assigned_at=datetime.now(UTC))
            )

        if first_name is not None or last_name is not None or organization is not None:
            data.profile = m.UserProfile(
                first_name=first_name,
                last_name=last_name,
                organization=organization,
            )
        return data


class RoleService(SQLAlchemyAsyncRepositoryService[m.Role]):
    """Handles database operations for users."""

    class Repository(SQLAlchemyAsyncSlugRepository[m.Role]):
        """User SQLAlchemy Repository."""

        model_type = m.Role

    repository_type = Repository
    match_fields = ["name"]

    async def to_model_on_create(self, data: ModelDictT[m.Role]) -> ModelDictT[m.Role]:
        data = schema_dump(data)
        if is_dict_without_field(data, "slug"):
            data["slug"] = await self.repository.get_available_slug(data["name"])
        return data

    async def to_model_on_update(self, data: ModelDictT[m.Role]) -> ModelDictT[m.Role]:
        data = schema_dump(data)
        if is_dict_without_field(data, "slug") and is_dict_with_field(data, "name"):
            data["slug"] = await self.repository.get_available_slug(data["name"])
        return data


class UserRoleService(SQLAlchemyAsyncRepositoryService[m.UserRole]):
    """Handles database operations for user roles."""

    class Repository(SQLAlchemyAsyncRepository[m.UserRole]):
        """User Role SQLAlchemy Repository."""

        model_type = m.UserRole

    repository_type = Repository
