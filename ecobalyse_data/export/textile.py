import json
from typing import List

import orjson

from common.export import (
    format_json,
)
from ecobalyse_data.logging import logger
from models.process import Material


def activities_to_materials_json(
    activities_path: str, materials_paths: List[str]
) -> List[Material]:
    logger.info(f"-> Loading activities file {activities_path}")

    activities = []
    with open(activities_path, "r") as file:
        activities = json.load(file)

    materials = activities_to_materials(activities)

    materials_dict = [material.model_dump() for material in materials]

    exported_files = []
    for materials_path in materials_paths:
        with open(materials_path, "wb") as output_file:
            output_file.write(
                orjson.dumps(
                    materials_dict, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS
                )
            )

            exported_files.append(materials_path)

    format_json(" ".join(exported_files))

    for materials_path in exported_files:
        logger.info(f"-> Exported {len(materials_dict)} materials to {materials_path}")


def activities_to_materials(activities: List[dict]) -> List[Material]:
    return [
        activity_to_material(activity)
        for activity in list(activities)
        if activity["category"] == "material"
    ]


def activity_to_material(activity: dict) -> Material:
    return Material(
        id=activity["material_id"],
        materialProcessUuid=activity["id"],
        recycledProcessUuid=activity.get("recycledProcessUuid"),
        recycledFrom=activity.get("recycledFrom"),
        name=activity["shortName"],
        shortName=activity["shortName"],
        origin=activity["origin"],
        primary=activity.get("primary"),
        geographicOrigin=activity["geographicOrigin"],
        defaultCountry=activity["defaultCountry"],
        cff=activity.get("cff"),
    )
