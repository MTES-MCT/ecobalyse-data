from __future__ import annotations

from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from app.domain.components import urls
from app.domain.components.deps import provide_components_service
from app.domain.components.schemas import Component, ComponentCreate, ComponentUpdate
from app.lib.deps import create_filter_dependencies
from litestar import get, patch, post
from litestar.controller import Controller
from litestar.di import Provide
from litestar.params import Dependency, Parameter

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
    async def list_components(
        self,
        components_service: ComponentService,
        filters: Annotated[list[FilterTypes], Dependency(skip_validation=True)],
    ) -> OffsetPagination[Component]:
        """List components."""
        results, total = await components_service.list_and_count(
            *filters, uniquify=True
        )

        return components_service.to_schema(
            data=results, total=total, schema_type=Component, filters=filters
        )

    @post(operation_id="CreateComponent", path=urls.COMPONENT_CREATE)
    async def create_component(
        self, components_service: ComponentService, data: ComponentCreate
    ) -> Component:
        """Create a new component."""
        db_obj = await components_service.create(data.to_dict())
        return components_service.to_schema(db_obj, schema_type=Component)

    @patch(operation_id="UpdateComponent", path=urls.COMPONENT_UPDATE)
    async def update_component(
        self,
        data: ComponentUpdate,
        components_service: ComponentService,
        component_id: UUID = Parameter(
            title="Component ID", description="The component to update."
        ),
    ) -> Component:
        """Update a component."""
        db_obj = await components_service.update(
            item_id=component_id, data=data.to_dict(), uniquify=True
        )
        return components_service.to_schema(db_obj, schema_type=Component)

    @patch(operation_id="BulkUpdateComponent", path=urls.COMPONENT_BULK_UPDATE)
    async def bulk_update_component(
        self,
        data: list[ComponentUpdate],
        components_service: ComponentService,
    ) -> Component:
        """Update a list of components."""
        db_obj = await components_service.upsert_many(data=data, uniquify=True)
        return components_service.to_schema(db_obj, schema_type=Component)
