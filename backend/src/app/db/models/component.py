from __future__ import annotations

from typing import Any

from advanced_alchemy.base import UUIDAuditBase
from sqlalchemy.orm import Mapped
from sqlalchemy.types import JSON


class ComponentModel(UUIDAuditBase):
    type_annotation_map = {dict[str, Any]: JSON}
    __tablename__ = "component"
    elements: Mapped[dict[str, Any]]
    name: Mapped[str]
