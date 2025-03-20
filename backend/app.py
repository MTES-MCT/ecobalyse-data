from litestar import Litestar, get, post
from litestar.contrib.sqlalchemy.repository import SQLAlchemyAsyncRepository
from litestar.controller import Controller
from litestar.di import Provide
from litestar.plugins.sqlalchemy import (
    AsyncSessionConfig,
    EngineConfig,
    SQLAlchemyAsyncConfig,
    SQLAlchemyInitPlugin,
    SQLAlchemySerializationPlugin,
    base,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped


class ComponentModel(base.UUIDBase):
    __tablename__ = "components"
    name: Mapped[str]


class ComponentRepository(SQLAlchemyAsyncRepository[ComponentModel]):
    """Component repository."""

    model_type = ComponentModel


async def provide_components_repo(db_session: AsyncSession) -> ComponentRepository:
    """This provides the default Components repository."""

    return ComponentRepository(session=db_session)


class ComponentController(Controller):
    """Component CRUD"""

    dependencies = {"components_repo": Provide(provide_components_repo)}

    @get(path="/components")
    async def list_components(
        self,
        components_repo: ComponentRepository,
    ) -> list[ComponentModel]:
        """List components."""

        results, total = await components_repo.list_and_count()

        return results

    @post(path="/components")
    async def create_component(
        self,
        components_repo: ComponentRepository,
        data: ComponentModel,
    ) -> ComponentModel:
        """Create a new component."""

        obj = await components_repo.add(data)

        await components_repo.session.commit()

        return obj


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
