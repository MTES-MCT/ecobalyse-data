from __future__ import annotations

from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from app.domain.components import urls
from app.domain.components.deps import provide_components_service
from app.domain.components.schemas import Component
from app.lib.deps import create_filter_dependencies
from litestar import get
from litestar.controller import Controller
from litestar.di import Provide
from litestar.params import Dependency

if TYPE_CHECKING:
    from advanced_alchemy.filters import FilterTypes
    from advanced_alchemy.service import OffsetPagination
    from app.domain.components.services import ComponentService


class ComponentController(Controller):
    """Component CRUD"""

    dependencies = {
        "components_service": Provide(provide_components_service)
    } | create_filter_dependencies(
        {
            "id_filter": UUID,
            "search": "name",
            "pagination_type": "limit_offset",
            "pagination_size": 20,
            "created_at": True,
            "updated_at": True,
            "sort_field": "name",
            "sort_order": "asc",
        },
    )

    tags = ["Components"]

    @get(operation_id="ListComponents", path=urls.COMPONENT_LIST, cache=60)
    async def list_users(
        self,
        components_service: ComponentService,
        filters: Annotated[list[FilterTypes], Dependency(skip_validation=True)],
    ) -> OffsetPagination[Component]:
        """List components."""
        results, total = await components_service.list_and_count(*filters)
        return components_service.to_schema(
            data=results, total=total, schema_type=Component, filters=filters
        )

    # @post(
    #     path="/components",
    #     dto=UpdateComponentDTO,
    #     return_dto=SQLAlchemyDTO[ComponentModel],
    # )
    # async def create_component(
    #     self,
    #     components_repo: ComponentRepository,
    #     data: ComponentModel,
    # ) -> ComponentModel:
    #     """Create a new component."""
    #
    #     obj = await components_repo.add(data)
    #
    #     await components_repo.session.commit()
    #
    #     return obj
    #
    # @patch(
    #     path="/components/{component_id:uuid}",
    #     dto=UpdateComponentDTO,
    #     return_dto=SQLAlchemyDTO[ComponentModel],
    # )
    # async def update_component(
    #     self,
    #     components_repo: ComponentRepository,
    #     data: ComponentModel,
    #     component_id: UUID = Parameter(
    #         title="Component ID",
    #         description="The component to update.",
    #     ),
    # ) -> ComponentModel:
    #     """Update a component."""
    #
    #     obj = await components_repo.update(
    #         ComponentModel(**{"id": component_id, "name": data.name}), uniquify=True
    #     )
    #
    #     await components_repo.session.commit()
    #
    #     return obj
