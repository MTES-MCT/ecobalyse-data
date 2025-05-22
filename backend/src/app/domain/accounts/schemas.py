from __future__ import annotations

from datetime import datetime  # noqa: TC003
from uuid import UUID  # noqa: TC003

from app.lib.schema import CamelizedBaseStruct

__all__ = (
    "AccountLogin",
    "User",
    "UserCreate",
    "UserRole",
    "UserRoleAdd",
    "UserRoleRevoke",
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
    terms_accepted: bool = False


class User(CamelizedBaseStruct):
    """User properties to use for a response."""

    id: UUID
    email: str
    profile: UserProfile
    is_superuser: bool = False
    is_active: bool = False
    is_verified: bool = False
    roles: list[UserRole] = []
    magic_link_sent_at: datetime | None = None


class UserCreate(CamelizedBaseStruct):
    email: str
    first_name: str
    last_name: str
    organization: str | None
    terms_accepted: bool = False
    is_superuser: bool = False
    is_active: bool = True
    is_verified: bool = False


class AccountLogin(CamelizedBaseStruct):
    email: str


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


class ApiToken(CamelizedBaseStruct):
    """Api token validation"""

    token: str


class ApiTokenFromDb(CamelizedBaseStruct):
    """Api token DB information"""

    id: UUID
    last_accessed_at: datetime | None = None


class ApiTokenCreate(CamelizedBaseStruct):
    """Api token creation"""

    hashed_token: str
    is_legacy: bool
    user_id: UUID
