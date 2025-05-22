import os

import orjson

from bin import export
from config import settings


def test_export_processes(forwast, tmp_path, processes_impacts_json):
    settings.set("OUTPUT_DIR", str(tmp_path))
    settings.set("LOCAL_EXPORT", False)
    settings.set("BASE_PATH", "tests/fixtures")

    export.processes(
        scopes=None,
        simapro=False,
        plot=False,
        verbose=False,
    )

    with open(os.path.join(tmp_path, "processes_impacts.json"), "rb") as f:
        json_data = orjson.loads(f.read())
        assert json_data == processes_impacts_json


def test_export_ingredients(forwast, tmp_path, ingredients_food_json):
    settings.set("OUTPUT_DIR", str(tmp_path))
    settings.set("LOCAL_EXPORT", False)
    settings.set("BASE_PATH", "tests/fixtures")

    output_path = os.path.join(tmp_path, "food")
    os.makedirs(output_path)

    export.metadata(scopes=[export.MetadataScope.food])

    with open(os.path.join(output_path, "ingredients.json"), "rb") as f:
        json_data = orjson.loads(f.read())
        assert json_data == ingredients_food_json


def test_export_materials(forwast, tmp_path, materials_textile_json):
    settings.set("OUTPUT_DIR", str(tmp_path))
    settings.set("LOCAL_EXPORT", False)
    settings.set("BASE_PATH", "tests/fixtures")

    output_path = os.path.join(tmp_path, "textile")
    os.makedirs(output_path)

    export.metadata(scopes=[export.MetadataScope.textile])

    with open(os.path.join(output_path, "materials.json"), "rb") as f:
        json_data = orjson.loads(f.read())
        assert json_data == materials_textile_json
