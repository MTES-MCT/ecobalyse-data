from __future__ import annotations

from typing import Annotated
from uuid import UUID

from litestar import Litestar, get, patch, post
from litestar.contrib.sqlalchemy.repository import SQLAlchemyAsyncRepository
from litestar.controller import Controller
from litestar.di import Provide
from litestar.dto import DTOConfig
from litestar.params import Parameter
from litestar.plugins.sqlalchemy import (
    AsyncSessionConfig,
    EngineConfig,
    SQLAlchemyAsyncConfig,
    SQLAlchemyDTO,
    SQLAlchemyInitPlugin,
    SQLAlchemySerializationPlugin,
    base,
)
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import Mapped


class ComponentModel(base.UUIDBase):
    __tablename__ = "component"
    name: Mapped[str]


class ComponentRepository(SQLAlchemyAsyncRepository[ComponentModel]):
    """Component repository."""

    model_type = ComponentModel


async def provide_components_repo(db_session: AsyncSession) -> ComponentRepository:
    """This provides the default Components repository."""

    return ComponentRepository(session=db_session)


UpdateComponentDTO = SQLAlchemyDTO[
    Annotated[
        ComponentModel,
        DTOConfig(
            exclude={
                "id",
            }
        ),
    ]
]


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

    @patch(
        path="/components/{component_id:uuid}",
        dto=UpdateComponentDTO,
        return_dto=SQLAlchemyDTO[ComponentModel],
    )
    async def update_component(
        self,
        components_repo: ComponentRepository,
        data: ComponentModel,
        component_id: UUID = Parameter(
            title="Component ID",
            description="The component to update.",
        ),
    ) -> ComponentModel:
        """Update a component."""

        print(f"#### -> {component_id}")
        obj = await components_repo.update(
            ComponentModel(**{"id": component_id, "name": data.name})
        )

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
