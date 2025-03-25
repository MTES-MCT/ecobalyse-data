from __future__ import annotations

from litestar import Litestar
from litestar.plugins.sqlalchemy import (
    AsyncSessionConfig,
    EngineConfig,
    SQLAlchemyAsyncConfig,
    SQLAlchemyInitPlugin,
    SQLAlchemySerializationPlugin,
    base,
)

from backend.src.controllers.component import ComponentController

session_config = AsyncSessionConfig(expire_on_commit=False)

sqlalchemy_config = SQLAlchemyAsyncConfig(
    connection_string="sqlite+aiosqlite:///ecobalyse-bo.db",
    session_config=session_config,
    engine_config=EngineConfig(echo=True),
)  # Create 'db_session' dependency.

sqlalchemy_plugin = SQLAlchemyInitPlugin(config=sqlalchemy_config)


async def on_startup() -> None:
    """Initializes the database."""

    async with sqlalchemy_config.get_engine().begin() as conn:
        await conn.run_sync(base.UUIDBase.metadata.create_all)


app = Litestar(
    route_handlers=[ComponentController],
    on_startup=[on_startup],
    plugins=[
        SQLAlchemySerializationPlugin(),
        SQLAlchemyInitPlugin(config=sqlalchemy_config),
    ],
)
