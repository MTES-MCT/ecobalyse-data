from __future__ import annotations

from advanced_alchemy.repository import (
    SQLAlchemyAsyncRepository,
)
from advanced_alchemy.service import (
    SQLAlchemyAsyncRepositoryService,
)
from app.db import models as m


class ComponentService(SQLAlchemyAsyncRepositoryService[m.ComponentModel]):
    """Handles database operations for users."""

    class ComponentRepository(SQLAlchemyAsyncRepository[m.ComponentModel]):
        """Component SQLAlchemy Repository."""

        model_type = m.ComponentModel

    repository_type = ComponentRepository
