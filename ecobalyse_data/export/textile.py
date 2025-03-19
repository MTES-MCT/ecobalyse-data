import json
from typing import List

from common.export import (
    export_json,
    format_json,
)
from ecobalyse_data.logging import logger
from models.process import Cff, Material


def activities_to_materials_json(
    activities_path: str, materials_paths: List[str]
) -> List[Material]:
    logger.info(f"-> Loading activities file {activities_path}")

    activities = []
    with open(activities_path, "r") as file:
        activities = json.load(file)

    materials = activities_to_materials(activities)

    materials_dict = [material.model_dump(by_alias=True) for material in materials]

    exported_files = []
    for materials_path in materials_paths:
        export_json(materials_dict, materials_path, sort=True)
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
    cff = activity.get("cff")

    if cff:
        cff = Cff(
            manufacturer_allocation=cff.get("manufacturerAllocation"),
            recycled_quality_ratio=cff.get("recycledQualityRatio"),
        )
    return Material(
        id=activity["material_id"],
        material_process_uuid=activity["id"],
        recycled_process_uuid=activity.get("recycledProcessUuid"),
        recycled_from=activity.get("recycledFrom"),
        name=activity["shortName"],
        short_name=activity["shortName"],
        origin=activity["origin"],
        primary=activity.get("primary"),
        geographic_origin=activity["geographicOrigin"],
        default_country=activity["defaultCountry"],
        cff=cff,
    )
