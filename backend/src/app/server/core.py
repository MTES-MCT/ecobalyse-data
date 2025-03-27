from __future__ import annotations

from typing import TypeVar

from click import Group
from litestar.config.app import AppConfig
from litestar.plugins import CLIPluginProtocol, InitPluginProtocol

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

        from uuid import UUID

        from app.config import app as config
        from app.config import get_settings
        from app.db import models as m
        from app.domain.components.controllers import ComponentController
        from app.domain.components.services import ComponentService
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
                plugins.problem_details,
            ],
        )

        # routes
        app_config.route_handlers.extend(
            [
                ComponentController,
            ],
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
        return app_config
