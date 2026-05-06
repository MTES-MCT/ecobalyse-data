"""Inference of baseIngredient from an alias."""

import functools
import json
from typing import Tuple

from config import PROJECT_ROOT_DIR

_BASE_INGREDIENTS_PATH = PROJECT_ROOT_DIR / "food" / "base_ingredients.json"


@functools.cache
def load_base_ingredients() -> Tuple[str, ...]:
    with open(_BASE_INGREDIENTS_PATH, "r", encoding="utf-8") as f:
        bps = json.load(f)
    return tuple(sorted(set(bps), key=len, reverse=True))


def infer_base_ingredient(alias: str) -> str:
    """Return the longest known baseIngredient that prefix-matches `alias`.

    Raises ValueError if no canonical baseIngredient prefix-matches the alias —
    contributors must register a new entry in `food/base_ingredients.json`.
    """
    for bp in load_base_ingredients():
        if alias == bp or alias.startswith(bp + "-"):
            return bp
    raise ValueError(
        f"Cannot infer baseIngredient for alias {alias!r}. "
        f"Add the canonical baseIngredient to food/base_ingredients.json."
    )
