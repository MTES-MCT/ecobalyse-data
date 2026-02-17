import json
from os.path import dirname, join

from config import settings
from ecobalyse_data.export import food

PROJECT_ROOT_DIR = dirname(dirname(__file__))


def test_load_ecs_dic(ecs_factors_csv_file, ecs_factors_json):
    content = food.load_ecosystemic_dic(ecs_factors_csv_file)

    assert len(content) == 35
    assert "AUTRES CULTURES INDUSTRIELLES" in content
    assert content["AUTRES CULTURES INDUSTRIELLES"]["cropDiversity"]["organic"] == 9.196


def test_feed_permanent_pasture():
    """Known grazing animal has permanent pasture feed"""
    feed_file_path = join(PROJECT_ROOT_DIR, "food", "ecosystemic_services", "feed.json")

    with open(feed_file_path) as f:
        content = json.load(f)

    animal = "lamb-meat-without-bone-organic"
    animal_feed = content[animal]

    permanent_key = settings.scopes.food.grazed_grass_permanent_key

    assert animal_feed.get(permanent_key, 0) > 0, (
        f"In {feed_file_path}, expected '{animal}' to have '{permanent_key}' > 0"
    )
