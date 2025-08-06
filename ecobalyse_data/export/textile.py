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

    return materials_dict


def activities_to_materials(activities: List[dict]) -> List[Material]:
    return [activity_to_material(activity) for activity in list(activities)]


def activity_to_material(eco_activity: dict) -> Material:
    textile_metadata = eco_activity["metadata"]["textile"]
    cff = textile_metadata.get("cff")

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

    return Material(
        alias=textile_metadata["alias"],
        id=eco_activity["id"],
        process_id=get_process_id(eco_activity, bw_activity),
        recycled_process_id=textile_metadata.get("recycledProcessId"),
        name=textile_metadata["name"],
        recycled_from=textile_metadata.get("recycledFrom"),
        origin=textile_metadata["origin"],
        primary=textile_metadata.get("primary"),
        geographic_origin=textile_metadata["geographicOrigin"],
        default_country=textile_metadata["defaultCountry"],
        cff=cff,
    )
