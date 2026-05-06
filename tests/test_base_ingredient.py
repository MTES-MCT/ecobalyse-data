from bin.export import _get_lcias
from common.base_ingredient import infer_base_ingredient
from config import PROJECT_ROOT_DIR


def _ingredient_aliases():
    """Yield every alias on an ingredient-category activity in lci_catalog/."""
    for activity in _get_lcias(PROJECT_ROOT_DIR):
        if "ingredient" not in activity.get("categories", []):
            continue
        for variant in activity.get("metadata", []):
            alias = variant.get("alias")
            if alias:
                yield alias


def test_infer_base_ingredient_covers_every_ingredient_alias():
    """Every ingredient alias must resolve to a known baseIngredient."""
    for alias in _ingredient_aliases():
        base_ingredient = infer_base_ingredient(alias)
        assert alias == base_ingredient or alias.startswith(base_ingredient + "-"), (
            f"inferred baseIngredient {base_ingredient!r} doesn't prefix-match alias {alias!r}"
        )
