from __future__ import annotations

from datetime import datetime  # noqa: TC003
from uuid import UUID  # noqa: TC003

import msgspec

from app.lib.schema import CamelizedBaseStruct

__all__ = (
    "AccountLogin",
    "AccountRegister",
    "User",
    "UserCreate",
    "UserRole",
    "UserRoleAdd",
    "UserRoleRevoke",
    "UserUpdate",
)


class UserRole(CamelizedBaseStruct):
    """Holds role details for a user.

    This is nested in the User Model for 'roles'
    """

    role_id: UUID
    role_slug: str
    role_name: str
    assigned_at: datetime


class UserProfile(CamelizedBaseStruct):
    """Holds profile details for a user.

    This is nested in the User Model for 'profile'
    """

    first_name: str
    last_name: str
    organization: str | None = None


class User(CamelizedBaseStruct):
    """User properties to use for a response."""

    id: UUID
    email: str
    profile: UserProfile
    is_superuser: bool = False
    is_active: bool = False
    is_verified: bool = False
    has_password: bool = False
    roles: list[UserRole] = []
    terms_accepted: bool = False
    magic_link_sent_at: datetime | None = None


class UserCreate(CamelizedBaseStruct):
    email: str
    password: str
    name: str | None = None
    is_superuser: bool = False
    is_active: bool = True
    is_verified: bool = False


class UserUpdate(CamelizedBaseStruct, omit_defaults=True):
    email: str | None | msgspec.UnsetType = msgspec.UNSET
    password: str | None | msgspec.UnsetType = msgspec.UNSET
    name: str | None | msgspec.UnsetType = msgspec.UNSET
    is_superuser: bool | None | msgspec.UnsetType = msgspec.UNSET
    is_active: bool | None | msgspec.UnsetType = msgspec.UNSET
    is_verified: bool | None | msgspec.UnsetType = msgspec.UNSET


class AccountLogin(CamelizedBaseStruct):
    email: str


class AccountRegister(CamelizedBaseStruct):
    email: str
    password: str
    name: str | None = None


class AccountRegisterMagicLink(CamelizedBaseStruct):
    email: str
    first_name: str
    last_name: str
    organization: str | None = None
    terms_accepted: bool = False
    is_active: bool = True


class UserRoleAdd(CamelizedBaseStruct):
    """User role add ."""

    user_name: str


class UserRoleRevoke(CamelizedBaseStruct):
    """User role revoke ."""

    user_name: str
