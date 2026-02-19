import os
from multiprocessing import Pool
from typing import List

import bw2data
import orjson

from common.export import export_json
from ecobalyse_data.bw.search import cached_search_one
from ecobalyse_data.export.land_occupation import compute_land_occupation
from ecobalyse_data.logging import logger
from models.process import (
    ObjectComplements,
    ProcessGeneric,
    ProcessGenericMetadata,
    Scope,
)


def _init_worker(project_name: str, base_dir: str):
    """Initialize Brightway project in worker process."""
    os.environ["BRIGHTWAY2_DIR"] = base_dir
    bw2data.projects.set_current(project_name)


def activities_to_processes_generic_json(
    activities: List[dict],
    processes_impacts_path: str,
    output_paths: List[str],
    cpu_count: int = 1,
) -> List[dict]:
    """Export denormalized processes_generic.json for object/veli scope.

    Combines process impacts with forest complements into a single file.
    Each activity is expanded into one entry per metadata.object variant.
    """
    # Load processes impacts and index by id
    with open(processes_impacts_path, "rb") as f:
        processes_list = orjson.loads(f.read())
    processes_by_id = {p["id"]: p for p in processes_list}

    # Compute land occupations only for activities that need it (have forestManagement)
    activities_needing_land = [
        a
        for a in activities
        if any(
            v.get("forestManagement") for v in a.get("metadata", {}).get("object", [])
        )
    ]
    if activities_needing_land:
        activities_needing_land = add_land_occupations(
            activities_needing_land, cpu_count
        )
        # Update activities in-place with computed land occupation data
        land_by_id = {a["id"]: a for a in activities_needing_land}
        activities = [land_by_id.get(a["id"], a) for a in activities]

    # Build denormalized entries
    generic_list = []

    for activity in activities:
        process = processes_by_id.get(activity["id"])
        if not process:
            raise ValueError(
                f"Process not found for activity {activity.get('displayName')} "
                f"(id: {activity['id']})"
            )

        # Temporary : if there is no object metadata just get the activity.id
        variants = activity.get("metadata", {}).get("object", [{"id": activity["id"]}])

        for variant in variants:
            has_forest = variant.get("forestManagement") is not None
            metadata = None
            if has_forest:
                forest = compute_forest_complement(
                    variant.get("forestManagement"),
                    variant.get("landOccupation"),
                )
                complements = ObjectComplements(forest=forest)
                metadata = ProcessGenericMetadata(
                    forest_management=variant.get("forestManagement"),
                    complements=complements,
                )

            entry = ProcessGeneric(
                activity_name=process["activityName"],
                categories=process["categories"],
                comment=process.get("comment", ""),
                display_name=variant.get(
                    "displayName", activity.get("displayName", "")
                ),
                elec_mj=process.get("elecMJ", 0),
                heat_mj=process.get("heatMJ", 0),
                id=variant["id"],
                impacts=process["impacts"],
                location=process.get("location"),
                mass_per_unit=process.get("massPerUnit"),
                metadata=metadata,
                scopes=[Scope(s) for s in activity.get("scopes", [])],
                source=process["source"],
                unit=process.get("unit"),
                waste=process.get("waste", 0),
            )
            generic_list.append(entry)

    # Sort and export
    generic_dicts = []
    for g in generic_list:
        d = g.model_dump(by_alias=True)
        generic_dicts.append(d)
    generic_dicts.sort(key=lambda x: x["id"])

    for output_path in output_paths:
        export_json(generic_dicts, output_path)
        logger.info(f"Exported {len(generic_dicts)} processes_generic to {output_path}")

    return generic_dicts


def add_land_occupation(activity: dict) -> dict:
    """Add land occupation data to an object activity.

    Computes land occupation using Brightway data and applies it to all
    entries in the object metadata list.

    Args:
        activity: A dictionary representing an object activity with metadata

    Returns:
        The activity dictionary with land occupation data added to object metadata
    """
    object_meta_list = activity.get("metadata", {}).get("object")
    if not object_meta_list or not isinstance(object_meta_list, list):
        return activity

    try:
        bw_activity = cached_search_one(
            activity.get("source"),
            activity.get("activityName"),
            location=activity.get("location"),
        )
        land_occupation = compute_land_occupation(bw_activity)
    except ValueError as e:
        logger.warning(
            f"Could not compute land occupation for {activity.get('displayName')}: {e}"
        )
        land_occupation = None

    # Apply land occupation to all entries in the list
    for meta in object_meta_list:
        meta["landOccupation"] = land_occupation

    return activity


def add_land_occupations(activities: List[dict], cpu_count: int) -> List[dict]:
    """Add land occupation to all activities using multiprocessing."""
    project_name = bw2data.projects.current
    base_dir = str(bw2data.projects._base_data_dir)

    with Pool(
        cpu_count, initializer=_init_worker, initargs=(project_name, base_dir)
    ) as pool:
        return pool.map(add_land_occupation, activities)


# Forest Management Coefficients
# ==============================
# Formula: forestComplement = landOccupation × coefficient[forestManagement]
#
# Reference values (from pine-softwood-intensive-plantation on ecobalyse.beta.gouv.fr), forestManagement = intensivePlantation:
#   - ldu impact = 4.316 Pts/kg (displayed as 4316 mPts)
#   - landOccupation = 1563 m².year
#
# coefficient calculation:
#   coefficient = (percentage × ldu) / landOccupation
#   For intensivePlantation, percentage = 25%: coefficient[intensivePlantation] = 0.25 × 4.316 / 1563 ≈ 0.00069
#
# Positive = malus (adds impact), Negative = bonus (reduces impact)

LDU_IMPACT_BY_LAND_OCCUPATION = 4.316 / 1563

FOREST_MANAGEMENT_COEFFICIENTS = {
    "diversifiedForest": -1 * LDU_IMPACT_BY_LAND_OCCUPATION * 0.25,  # bonus 25% ldu
    "certifiedDiversifiedForest": -1
    * LDU_IMPACT_BY_LAND_OCCUPATION
    * 0.35,  # bonus 35% ldu
    "intensivePlantation": LDU_IMPACT_BY_LAND_OCCUPATION * 0.25,  # malus 25% ldu
    "sustainableManagement": 0,
    "certifiedSustainableManagement": -1
    * LDU_IMPACT_BY_LAND_OCCUPATION
    * 0.1,  # bonus 10% ldu
}


def compute_forest_complement(
    forest_management: str | None, land_occupation: float | None
) -> float:
    """Compute forest complement from forestManagement type and land occupation.

    Returns landOccupation * coefficient(forestManagement), or null if either is None.
    """
    if forest_management is None or land_occupation is None:
        return None

    coefficient = FOREST_MANAGEMENT_COEFFICIENTS[forest_management]
    return land_occupation * coefficient
