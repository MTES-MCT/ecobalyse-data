from __future__ import annotations

from typing import List, Optional
from uuid import UUID

from litestar.contrib.sqlalchemy.repository import SQLAlchemyAsyncRepository
from litestar.plugins.sqlalchemy import (
    base,
)
from sqlalchemy import Column, ForeignKey, Table
from sqlalchemy.orm import Mapped, mapped_column, relationship


class ComponentModel(base.UUIDBase):
    __tablename__ = "component"
    name: Mapped[str]

    elements: Mapped[list[ComponentElement]] = relationship(
        back_populates="component", lazy="joined"
    )


class ComponentRepository(SQLAlchemyAsyncRepository[ComponentModel]):
    """Component repository."""

    model_type = ComponentModel


component_element_transform_table = Table(
    "component_element_transform_table",
    base.DefaultBase.metadata,
    Column(
        "component_element_id", ForeignKey("component_element.id"), primary_key=True
    ),
    Column("process_id", ForeignKey("process.id"), primary_key=True),
)


class ProcessModel(base.UUIDBase):
    __tablename__ = "process"
    display: Mapped[Optional[str]]
    name: Mapped[str]

    elements: Mapped[list[ComponentElement]] = relationship(
        back_populates="material", lazy="joined"
    )

    transform_elements: Mapped[List[ComponentElement]] = relationship(
        secondary=component_element_transform_table, back_populates="transforms"
    )


class ProcessRepository(SQLAlchemyAsyncRepository[ProcessModel]):
    """Process repository."""

    model_type = ProcessModel


class ComponentElement(base.UUIDBase):
    __tablename__ = "component_element"

    component_id: Mapped[UUID] = mapped_column(ForeignKey("component.id"))

    component: Mapped[ComponentModel] = relationship(
        lazy="joined", innerjoin=True, viewonly=True
    )

    material_id: Mapped[UUID] = mapped_column(ForeignKey("process.id"))

    material: Mapped[ProcessModel] = relationship(
        lazy="joined", innerjoin=True, viewonly=True
    )

    transforms: Mapped[List[ProcessModel]] = relationship(
        secondary=component_element_transform_table, back_populates="transform_elements"
    )
