from __future__ import annotations

from advanced_alchemy.base import UUIDAuditBase
from sqlalchemy.orm import Mapped, relationship

from .component_element import ComponentElement


class ComponentModel(UUIDAuditBase):
    __tablename__ = "component"
    name: Mapped[str]

    elements: Mapped[list[ComponentElement]] = relationship(
        back_populates="component", lazy="joined"
    )
