import json

from config import PROJECT_ROOT_DIR, settings
from ecobalyse_data.export import food


def test_load_ecs_dic(ecs_factors_csv_file, ecs_factors_json):
    content = food.load_ecosystemic_dic(ecs_factors_csv_file)

    assert len(content) == 35
    assert "AUTRES CULTURES INDUSTRIELLES" in content
    assert content["AUTRES CULTURES INDUSTRIELLES"]["cropDiversity"]["organic"] == 9.196


def test_feed_permanent_pasture():
    """Known grazing live animal has permanent pasture in its feed"""
    feed_file_path = PROJECT_ROOT_DIR / "food" / "ecosystemic_services" / "feed.json"

    with open(feed_file_path) as f:
        content = json.load(f)

    animal = "lamb-organic-national-average-farm-gate-fr-u-live"
    animal_feed = content[animal]

    permanent_key = settings.scopes.food.grazed_grass_permanent_key

    assert animal_feed.get(permanent_key, 0) > 0, (
        f"In {feed_file_path}, expected '{animal}' to have '{permanent_key}' > 0"
    )


def test_animal_to_meat_keys_in_feed():
    """Every live animal in animal_to_meat.json must exist in feed.json"""
    es_dir = PROJECT_ROOT_DIR / "food" / "ecosystemic_services"

    with open(es_dir / "feed.json") as f:
        feed = json.load(f)
    with open(es_dir / "animal_to_meat.json") as f:
        animal_to_meat = json.load(f)

    for animal_alias in animal_to_meat:
        assert animal_alias in feed, (
            f"Live animal '{animal_alias}' from animal_to_meat.json not found in feed.json"
        )


def test_resolve_feed_direct():
    """Direct products (milk, eggs) resolve from feed.json directly"""
    feed = {"milk-2025": {"grass": 0.5}}
    animal_to_meat = {}
    meat_to_animal_feed = food.build_meat_to_animal_feed(animal_to_meat)

    result = food.resolve_feed("milk-2025", feed, meat_to_animal_feed)
    assert result == {"grass": 0.5}


def test_resolve_feed_via_ratio():
    """Meat products resolve via live animal feed × ratio"""
    feed = {"pig-live": {"wheat": 1.0, "corn": 2.0}}
    animal_to_meat = {"pig-live": {"bacon": 2.16}}
    meat_to_animal_feed = food.build_meat_to_animal_feed(animal_to_meat)

    result = food.resolve_feed("bacon", feed, meat_to_animal_feed)
    assert result == {"wheat": 2.16, "corn": 4.32}


def test_resolve_feed_unknown():
    """Unknown alias returns None"""
    result = food.resolve_feed("unknown", {}, {})
    assert result is None
