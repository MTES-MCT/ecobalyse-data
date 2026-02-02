import os
from multiprocessing import Pool
from typing import List

import bw2data

from common.export import export_json
from ecobalyse_data.bw.search import cached_search_one
from ecobalyse_data.export.land_occupation import compute_land_occupation
from ecobalyse_data.logging import logger
from models.process import ObjectComplements, ObjectMetadata, Scope


def _init_worker(project_name: str, base_dir: str):
    """Initialize Brightway project in worker process."""
    os.environ["BRIGHTWAY2_DIR"] = base_dir
    bw2data.projects.set_current(project_name)


def activities_to_metadata_json(
    activities: List[dict], metadata_paths: List[str], cpu_count: int = 1
) -> List[dict]:
    """Export object metadata to JSON files."""
    activities_with_land_occupation = add_land_occupations(activities, cpu_count)
    metadata_list = activities_to_metadata_list(activities_with_land_occupation)
    metadata_dicts = [m.model_dump(by_alias=True) for m in metadata_list]
    metadata_dicts.sort(key=lambda x: x["id"])

    for metadata_path in metadata_paths:
        export_json(metadata_dicts, metadata_path)
        logger.info(
            f"Exported {len(metadata_dicts)} object metadata to {metadata_path}"
        )

    return metadata_dicts


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


def activities_to_metadata_list(activities: List[dict]) -> List[ObjectMetadata]:
    """Convert activities with object metadata to ObjectMetadata list."""
    metadata_list = []
    for activity in activities:
        metas = activity_to_metadata_list(activity)
        metadata_list.extend(metas)
    return metadata_list


def activity_to_metadata_list(eco_activity: dict) -> List[ObjectMetadata]:
    """Extract list of ObjectMetadata from a single activity."""
    object_meta_list = eco_activity.get("metadata", {}).get("object")
    if not object_meta_list or not isinstance(object_meta_list, list):
        return []

    result = []
    for object_meta in object_meta_list:
        forest = compute_forest_complement(
            object_meta.get("forestManagement"),
            object_meta.get("landOccupation"),
        )
        complements = ObjectComplements(forest=forest)

        result.append(
            ObjectMetadata(
                id=object_meta["id"],
                alias=object_meta["alias"],
                process_id=eco_activity["id"],
                scopes=[Scope(s) for s in eco_activity.get("scopes", [])],
                complements=complements,
                land_occupation=object_meta.get("landOccupation"),
                forest_management=object_meta.get("forestManagement"),
            )
        )

    return result


# for pine-softwood-intensive-plantation ldu impact per kg is 4.316 Pts/kg (as seen on www.ecobalyse.beta.gouv.fr. In fact its displayed as 4316 Pts because we display mPts not Pts)
# for intensivePlantation we want complement to add an impact of ~25% ldu
# formula is landOccupation * coefficient(forestManagement) = forestComplement
# landOccupation = 1563 m2.an
#  coefficient(intensivePlantation) = forestComplement / landOccupation


# for intensivePlantation :
#  coefficient(intensivePlantation) = 0.25*ldu / landOccupation
#  coefficient(intensivePlantation) = 0.25*4316 / 1563 ~ 0.69


FOREST_MANAGEMENT_COEFFICIENTS = {
    "diversifiedForest": -0.00069,  # bonus 25% ldu
    "certifiedDiversifiedForest": -0.00097,  # bonus 35% ldu
    "intensivePlantation": 0.00069,  # malus 25% ldu
    "sustainableManagement": 0,
    "certifiedSustainableManagement": -0000.28,  # bonus 10% ldu
}


def compute_forest_complement(
    forest_management: str | None, land_occupation: float | None
) -> float:
    """Compute forest complement from forestManagement type and land occupation.

    Returns landOccupation * coefficient(forestManagement), or 0 if either is None.
    """
    if forest_management is None or land_occupation is None:
        return 0

    coefficient = FOREST_MANAGEMENT_COEFFICIENTS.get(forest_management, 0)
    return land_occupation * coefficient
