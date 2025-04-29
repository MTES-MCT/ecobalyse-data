from __future__ import annotations

from typing import Any

from app.config import get_settings
from litestar.connection import ASGIConnection
from litestar.exceptions import PermissionDeniedException


class UserService:
    """Handles operations for users."""

    async def retrieve_user_handler(
        session: dict[str, Any], connection: "ASGIConnection[Any, Any, Any, Any]"
    ) -> str | None:
        return user_token if (user_token := session.get("user_token")) else None

    async def authenticate(self, token: str) -> bool:
        settings = get_settings()
        """Authenticate a user against Django API."""
        # @TODO: call the Django auth API
        print(settings.auth.AUTH_ENDPOINT)
        if not token:
            msg = "A token must be provided"
            raise PermissionDeniedException(detail=msg)

        return False
