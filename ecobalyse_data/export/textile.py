from typing import List

from common.export import export_json, format_json
from common.utils import get_process_id
from ecobalyse_data.bw.search import cached_search_one
from ecobalyse_data.logging import logger
from models.process import Cff, Material


def activities_to_materials_json(
    activities: List[dict], materials_paths: List[str]
) -> List[Material]:
    materials = activities_to_materials_list(activities)

    materials_dict = [material.model_dump(by_alias=True) for material in materials]

    exported_files = []
    for materials_path in materials_paths:
        export_json(materials_dict, materials_path, sort=True)
        exported_files.append(materials_path)

    format_json(" ".join(exported_files))

    for materials_path in exported_files:
        logger.info(f"-> Exported {len(materials_dict)} materials to {materials_path}")

    return materials_dict


def activities_to_materials_list(activities: List[dict]) -> List[Material]:
    materials = []
    for activity in activities:
        materials.extend(activity_to_materials(activity))
    return materials


def activity_to_materials(eco_activity: dict) -> List[Material]:
    materials = []
    bw_activity = {}

    if eco_activity.get("source") != "Custom":
        bw_activity = cached_search_one(
            eco_activity.get("source"),
            eco_activity.get("activityName"),
            location=eco_activity.get("location"),
        )

    for textile_metadata in eco_activity["metadata"]["textile"]:
        cff = textile_metadata.get("cff")

        if cff:
            cff = Cff(
                manufacturer_allocation=cff.get("manufacturerAllocation"),
                recycled_quality_ratio=cff.get("recycledQualityRatio"),
            )

        materials.append(
            Material(
                alias=textile_metadata["alias"],
                id=textile_metadata["id"],
                process_id=get_process_id(eco_activity, bw_activity),
                display_name=textile_metadata["displayName"],
                recycled_from=textile_metadata.get("recycledFrom"),
                origin=textile_metadata["origin"],
                primary=textile_metadata.get("primary"),
                geographic_origin=textile_metadata["geographicOrigin"],
                default_country=textile_metadata["defaultCountry"],
                cff=cff,
            )
        )
    return materials
