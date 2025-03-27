from __future__ import annotations

from typing import TYPE_CHECKING, Annotated
from uuid import UUID

from app.domain.components import urls
from app.domain.components.deps import provide_components_service
from app.domain.components.schemas import Component, ComponentUpdate
from app.lib.deps import create_filter_dependencies
from litestar import get, patch
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

    @patch(operation_id="BulkUpdateComponent", path=urls.COMPONENT_BULK_UPDATE)
    async def bulk_update_component(
        self,
        data: list[ComponentUpdate],
        components_service: ComponentService,
    ) -> Component:
        """Update a list of components."""
        components = await components_service.upsert_many(data=data, uniquify=True)

        return components_service.to_schema(components, schema_type=Component)
