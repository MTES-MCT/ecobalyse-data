from __future__ import annotations

from typing import TYPE_CHECKING, List
from uuid import UUID

from advanced_alchemy.base import UUIDAuditBase
from sqlalchemy import ForeignKey, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship

if TYPE_CHECKING:
    from .component import ComponentModel
    from .process import ProcessModel


class ComponentElement(UUIDAuditBase):
    __tablename__ = "component_element"

    amount: Mapped[float]

    component_id: Mapped[UUID] = mapped_column(ForeignKey("component.id"))

    component: Mapped[ComponentModel] = relationship(
        lazy="joined", innerjoin=True, viewonly=True
    )

    material_id: Mapped[UUID] = mapped_column(ForeignKey("process.id"))

    material: Mapped[ProcessModel] = relationship(
        lazy="joined", innerjoin=True, viewonly=True
    )

    transforms: Mapped[List[ProcessModel]] = relationship(
        secondary=lambda: _component_element_transform(),
        back_populates="transform_elements",
    )


def _component_element_transform() -> Table:
    from .component_element_transform import component_element_transform_table

    return component_element_transform_table
