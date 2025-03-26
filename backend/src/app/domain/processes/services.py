from __future__ import annotations

from typing import TYPE_CHECKING

from advanced_alchemy.repository import (
    SQLAlchemyAsyncRepository,
)
from advanced_alchemy.service import (
    SQLAlchemyAsyncRepositoryService,
    schema_dump,
)
from app.db import models as m

if TYPE_CHECKING:
    from advanced_alchemy.service import ModelDictT

__all__ = ("ProcessService",)


class ProcessService(SQLAlchemyAsyncRepositoryService[m.ProcessModel]):
    """Handles database operations for processes."""

    class ProcessRepository(SQLAlchemyAsyncRepository[m.ProcessModel]):
        """Process SQLAlchemy Repository."""

        model_type = m.ProcessModel

    repository_type = ProcessRepository

    match_fields = ["name"]

    async def to_model_on_upsert(
        self, data: ModelDictT[m.ProcessModel]
    ) -> ModelDictT[m.ProcessModel]:
        data = schema_dump(data)
        print(f"###### -> to model on upsert {data}")
        return data
