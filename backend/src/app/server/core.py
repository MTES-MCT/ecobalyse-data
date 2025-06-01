from __future__ import annotations

from pathlib import Path
from typing import Any, TypeVar
from uuid import UUID

from app.domain.accounts.schemas import DjangoUser
from click import Group
from litestar.config.app import AppConfig
from litestar.connection import ASGIConnection
from litestar.middleware.session.server_side import (
    ServerSideSessionBackend,
    ServerSideSessionConfig,
)
from litestar.plugins import CLIPluginProtocol, InitPluginProtocol
from litestar.security.session_auth import SessionAuth
from litestar.stores.file import FileStore

T = TypeVar("T")


class ApplicationCore(InitPluginProtocol, CLIPluginProtocol):
    """Application core configuration plugin.

    This class is responsible for configuring the main Litestar application with our routes, guards, and various plugins

    """

    __slots__ = "app_slug"
    app_slug: str

    def on_cli_init(self, cli: Group) -> None:
        from app.cli.commands import fixtures_management_group
        from app.config import get_settings

        settings = get_settings()
        self.app_slug = settings.app.slug
        cli.add_command(fixtures_management_group)

    def on_app_init(self, app_config: AppConfig) -> AppConfig:
        """Configure application for use with SQLAlchemy.

        Args:
            app_config: The :class:`AppConfig <litestar.config.app.AppConfig>` instance.
        """

        from app.config import app as config
        from app.config import get_settings
        from app.db import models as m
        from app.domain.accounts.controllers import AccessController
        from app.domain.components.controllers import ComponentController
        from app.domain.components.services import ComponentService
        from app.domain.system.controllers import SystemController
        from app.server import plugins
        from litestar.enums import RequestEncodingType
        from litestar.params import Body

        settings = get_settings()
        self.app_slug = settings.app.slug
        app_config.debug = settings.app.DEBUG
        # security
        app_config.cors_config = config.cors
        # plugins
        app_config.plugins.extend(
            [
                plugins.structlog,
                plugins.alchemy,
                plugins.granian,
                plugins.problem_details,
            ],
        )

        # routes
        app_config.route_handlers.extend(
            [AccessController, ComponentController, SystemController],
        )
        # signatures
        app_config.signature_namespace.update(
            {
                "RequestEncodingType": RequestEncodingType,
                "Body": Body,
                "m": m,
                "UUID": UUID,
                "ComponentService": ComponentService,
            },
        )

        # middlewares
        # auth_mw = DefineMiddleware(DjangoAuthenticationMiddleware)
        app_config.middleware.extend([ServerSideSessionConfig().middleware])

        app_config.stores = {"sessions": FileStore(path=Path("session_data"))}

        # The SessionAuth class requires a handler callable
        # that takes the session dictionary, and returns the
        # 'User' instance correlating to it.
        #
        # The session dictionary itself is a value the user decides
        # upon. So for example, it might be a simple dictionary
        # that holds a user id, for example: { "id": "abcd123" }
        #
        # Note: The callable can be either sync or async - both will work.
        async def retrieve_user_handler(
            session: dict[str, Any], connection: "ASGIConnection[Any, Any, Any, Any]"
        ) -> DjangoUser | None:
            import requests

            if session_user := session.get("user"):
                return session_user

            TOKEN_HEADER = "token"

            # retrieve the auth header
            auth_header = connection.headers.get(TOKEN_HEADER)
            if not auth_header:
                return None

            settings = get_settings()

            """Authenticate a user against Django API using the Token Auth."""
            response = requests.get(
                settings.auth.AUTH_ENDPOINT, headers={TOKEN_HEADER: auth_header}
            )
            user = response.json()
            if response.status_code != 200 or not user["staff"]:
                return None

            return DjangoUser(**user)

        session_auth = SessionAuth[DjangoUser, ServerSideSessionBackend](
            retrieve_user_handler=retrieve_user_handler,
            # we must pass a config for a session backend.
            # all session backends are supported
            session_backend_config=ServerSideSessionConfig(),
        )

        app_config = session_auth.on_app_init(app_config)

        return app_config
