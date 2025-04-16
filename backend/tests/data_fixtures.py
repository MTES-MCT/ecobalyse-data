from __future__ import annotations

from typing import TYPE_CHECKING, Any

import pytest

if TYPE_CHECKING:
    from app.db.models import ComponentModel
    from litestar import Litestar
    from pytest import MonkeyPatch


pytestmark = pytest.mark.anyio


@pytest.fixture(name="app")
def fx_app(pytestconfig: pytest.Config, monkeypatch: MonkeyPatch) -> Litestar:
    """App fixture.

    Returns:
        An application instance, configured via plugin.
    """
    from app.asgi import create_app

    return create_app()


@pytest.fixture(name="raw_components")
def fx_raw_components() -> list[ComponentModel | dict[str, Any]]:
    """Unstructured components representations."""

    return [
        {
            "id": "64fa65b3-c2df-4fd0-958b-83965bd6aa08",
            "name": "Pied 70 cm (plein bois)",
        },
        {
            "id": "ad9d7f23-076b-49c5-93a4-ee1cd7b53973",
            "name": "Dossier plastique (PP)",
        },
        {"id": "eda5dd7e-52e4-450f-8658-1876efc62bd6", "name": "Assise plastique (PP)"},
        {
            "id": "6f8d1621-324a-4c00-abe3-f90813d878d2",
            "name": "Pied 90 cm (plein bois)",
        },
        {
            "id": "3d1ba21f-a139-4e1f-8192-082327ad855e",
            "name": "Plateau 200x100 (chêne)",
        },
        {"id": "190276e9-5b90-42d6-8fbd-bc7ddfd4c960", "name": "Cadre plastique"},
        {"id": "8ca2ca05-8aec-4121-acaa-7cdcc03150a9", "name": "Tissu pour canapé"},
    ]
