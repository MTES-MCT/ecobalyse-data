from __future__ import annotations

from typing import List, Optional

from advanced_alchemy.base import UUIDAuditBase
from sqlalchemy.orm import Mapped, relationship

from .component_element import ComponentElement
from .component_element_transform import component_element_transform_table


class ProcessModel(UUIDAuditBase):
    __tablename__ = "process"
    display: Mapped[Optional[str]]
    name: Mapped[str]

    transform_elements: Mapped[List[ComponentElement]] = relationship(
        secondary=component_element_transform_table, back_populates="transforms"
    )
