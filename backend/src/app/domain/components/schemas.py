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
    elements: list[dict]


class ComponentCreate(CamelizedBaseStruct):
    name: str


class ComponentUpdate(CamelizedBaseStruct, omit_defaults=True):
    id: UUID | None | msgspec.UnsetType = msgspec.UNSET
    name: str | None | msgspec.UnsetType = msgspec.UNSET

    elements: list[dict] | None | msgspec.UnsetType = msgspec.UNSET
