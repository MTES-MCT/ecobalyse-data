from __future__ import annotations

from datetime import date, datetime
from typing import TYPE_CHECKING

from advanced_alchemy.base import UUIDAuditBase
from sqlalchemy import String
from sqlalchemy.ext.hybrid import hybrid_property
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from .user_profile import UserProfile
    from .user_role import UserRole


class User(UUIDAuditBase):
    __tablename__ = "user_account"
    __table_args__ = {"comment": "User accounts for application access"}
    __pii_columns__ = {"email"}

    email: Mapped[str] = mapped_column(unique=True, index=True, nullable=False)
    hashed_password: Mapped[str | None] = mapped_column(
        String(length=255), nullable=True, default=None
    )
    magic_link_hashed_token: Mapped[str | None] = mapped_column(
        String(length=255), nullable=True, default=None
    )
    magic_link_sent_at: Mapped[date] = mapped_column(nullable=True, default=None)

    terms_accepted: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_superuser: Mapped[bool] = mapped_column(default=False, nullable=False)
    is_verified: Mapped[bool] = mapped_column(default=False, nullable=False)
    verified_at: Mapped[date] = mapped_column(nullable=True, default=None)
    joined_at: Mapped[date] = mapped_column(default=datetime.now)
    login_count: Mapped[int] = mapped_column(default=0)
    # -----------
    # ORM Relationships
    # ------------

    roles: Mapped[list[UserRole]] = relationship(
        back_populates="user",
        lazy="selectin",
        uselist=True,
        cascade="all, delete",
    )

    profile: Mapped[UserProfile] = relationship(
        back_populates="user", cascade="all, delete"
    )

    @hybrid_property
    def has_password(self) -> bool:
        return self.hashed_password is not None
