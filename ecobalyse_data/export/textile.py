from typing import List

from common.export import export_json, format_json, get_process_id
from ecobalyse_data.bw.search import cached_search_one
from ecobalyse_data.logging import logger
from models.process import Cff, Material


def activities_to_materials_json(
    activities: List[dict], materials_paths: List[str]
) -> List[Material]:
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
    return [activity_to_material(activity) for activity in list(activities)]


def activity_to_material(eco_activity: dict) -> Material:
    cff = eco_activity.get("cff")

    if cff:
        cff = Cff(
            manufacturer_allocation=cff.get("manufacturerAllocation"),
            recycled_quality_ratio=cff.get("recycledQualityRatio"),
        )

    bw_activity = {}

    if eco_activity.get("source") != "Custom":
        bw_activity = cached_search_one(
            eco_activity.get("source"), eco_activity.get("search")
        )

    # Use material_id as fallback when alias is null
    alias = eco_activity.get("alias") or eco_activity.get("material_id")

    return Material(
        alias=alias,
        id=eco_activity["id"],
        recycled_process_id=eco_activity.get("recycledProcessId"),
        recycled_from=eco_activity.get("recycledFrom"),
        name=eco_activity["shortName"],
        short_name=eco_activity["shortName"],
        origin=eco_activity["origin"],
        primary=eco_activity.get("primary"),
        geographic_origin=eco_activity["geographicOrigin"],
        default_country=eco_activity["defaultCountry"],
        cff=cff,
        process_id=get_process_id(eco_activity, bw_activity),
    )
