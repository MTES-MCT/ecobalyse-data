from __future__ import annotations

from advanced_alchemy.base import orm_registry
from sqlalchemy import Column, ForeignKey, Table

component_element_transform_table = Table(
    "component_element_transform_table",
    orm_registry.metadata,
    Column(
        "component_element_id",
        ForeignKey("component_element.id", ondelete="CASCADE"),
        primary_key=True,
    ),
    Column(
        "process_id", ForeignKey("process.id", ondelete="CASCADE"), primary_key=True
    ),
)
