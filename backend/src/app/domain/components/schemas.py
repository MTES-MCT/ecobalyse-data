from __future__ import annotations

from uuid import UUID  # noqa: TC003

import msgspec
from app.lib.schema import CamelizedBaseStruct

__all__ = (
    "Component",
    "ComponentCreate",
    "ComponentUpdate",
)


class Component(CamelizedBaseStruct):
    """Component properties to use for a response."""

    id: UUID
    name: str

    elements: list[ComponentElement] = []


class ComponentElement(CamelizedBaseStruct):
    """Component element properties to use for a response."""

    amount: float
    material_id: UUID = msgspec.field(name="material")


class ComponentCreate(CamelizedBaseStruct):
    name: str


class ComponentUpdate(CamelizedBaseStruct, omit_defaults=True):
    name: str | None | msgspec.UnsetType = msgspec.UNSET
