import os

import orjson

from bin import export
from config import settings


def test_export_processes(
    forwast, tmp_path, processes_food_json, processes_textile_json
):
    settings.set("OUTPUT_DIR", str(tmp_path))
    food_output_path = os.path.join(tmp_path, "food")
    textile_output_path = os.path.join(tmp_path, "textile")
    os.makedirs(food_output_path)
    os.makedirs(textile_output_path)

    export.processes(
        domain=[export.Domain.food, export.Domain.textile],
        simapro=False,
        plot=False,
        verbose=False,
    )

    with open(os.path.join(food_output_path, "processes_impacts.json"), "rb") as f:
        json_data = orjson.loads(f.read())
        assert json_data == processes_food_json

    with open(os.path.join(textile_output_path, "processes_impacts.json"), "rb") as f:
        json_data = orjson.loads(f.read())
        assert json_data == processes_textile_json


def test_export_ingredients(forwast, tmp_path, ingredients_food_json):
    settings.set("OUTPUT_DIR", str(tmp_path))
    output_path = os.path.join(tmp_path, "food")
    os.makedirs(output_path)

    export.metadata(domain=[export.MetadataDomain.food])

    with open(os.path.join(output_path, "ingredients.json"), "rb") as f:
        json_data = orjson.loads(f.read())
        assert json_data == ingredients_food_json


def test_export_materials(forwast, tmp_path, materials_textile_json):
    settings.set("OUTPUT_DIR", str(tmp_path))
    output_path = os.path.join(tmp_path, "textile")
    os.makedirs(output_path)

    export.metadata(domain=[export.MetadataDomain.textile])

    with open(os.path.join(output_path, "materials.json"), "rb") as f:
        json_data = orjson.loads(f.read())
        assert json_data == materials_textile_json
