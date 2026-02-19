import os

import orjson

from bin import export
from common.export import export_json
from config import settings
from create_activities import create_activities


def test_export_processes(forwast, tmp_path, processes_impacts_json):
    settings.set("OUTPUT_DIR", str(tmp_path))
    create_activities("tests/activities_to_create.json")

    export.processes(scopes=None, simapro=False, plot=False, verbose=False, cpu_count=1)

    with open(os.path.join(tmp_path, "processes_impacts.json"), "rb") as f:
        json_data = orjson.loads(f.read())
        export_json(
            json_data, os.path.join(settings.BASE_PATH, "processes_impacts_output.json")
        )
        assert json_data == processes_impacts_json


def test_export_ingredients(forwast, tmp_path, ingredients_food_json):
    settings.set("OUTPUT_DIR", str(tmp_path))

    output_path = os.path.join(tmp_path, "food")
    os.makedirs(output_path)

    export.metadata(scopes=[export.MetadataScope.food])

    with open(os.path.join(output_path, "ingredients.json"), "rb") as f:
        json_data = orjson.loads(f.read())
        assert json_data == ingredients_food_json


def test_export_materials(forwast, tmp_path, materials_textile_json):
    settings.set("OUTPUT_DIR", str(tmp_path))

    output_path = os.path.join(tmp_path, "textile")
    os.makedirs(output_path)

    export.metadata(scopes=[export.MetadataScope.textile])

    with open(os.path.join(output_path, "materials.json"), "rb") as f:
        json_data = orjson.loads(f.read())
        assert json_data == materials_textile_json


def test_export_processes_generic(
    forwast, tmp_path, processes_impacts_json, processes_generic_json
):
    settings.set("OUTPUT_DIR", str(tmp_path))
    # Write process impacts so the generic export can load them
    export_json(
        processes_impacts_json,
        os.path.join(tmp_path, settings.processes_impacts_file),
    )

    export.metadata(scopes=[export.MetadataScope.object])

    with open(os.path.join(tmp_path, "processes_generic.json"), "rb") as f:
        json_data = orjson.loads(f.read())
        assert json_data == processes_generic_json
