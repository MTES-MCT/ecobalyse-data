import json
import os
from typing import List

import orjson
from frozendict import frozendict

from common import (
    get_normalization_weighting_factors,
)
from common.export import (
    IMPACTS_JSON,
    display_changes_from_json,
    export_processes_to_dirs,
    format_json,
    plot_impacts,
)
from common.impacts import impacts as impacts_py
from common.impacts import main_method
from ecobalyse_data.computation import compute_impacts, compute_processes_for_activities
from ecobalyse_data.logging import logger
from models.process import ComputedBy, Material, Process


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


def get_activities_by_id(activities, logger) -> frozendict:
    logger.info("-> Get activities by id...")
    return frozendict({activity["id"]: activity for activity in activities})


def activities_to_processes(
    activities_path: str,
    aggregated_relative_file_path: str,
    impacts_relative_file_path: str,
    dirs_to_export_to: List[str],
    graph_folder: str,
    plot: bool = False,
    verbose: bool = False,
    display_changes: bool = True,
):
    logger.debug(f"-> Loading activities file {activities_path}")

    activities = []
    with open(activities_path, "r") as file:
        activities = json.load(file)

    factors = get_normalization_weighting_factors(IMPACTS_JSON)
    processes: List[Process] = compute_processes_for_activities(
        activities, main_method, impacts_py, IMPACTS_JSON, factors
    )

    if plot:
        for process in processes:
            os.makedirs(graph_folder, exist_ok=True)
            if process.computed_by == ComputedBy.hardcoded:
                logger.warning(
                    f"-> The process '{process.name}' has harcoded impacts, it can’t be plot, skipping."
                )
                continue
            elif process.source == "Ecobalyse":
                logger.warning(
                    f"-> The process '{process.name}' has been constructed by 'Ecobalyse' and is not present in simapro, skipping."
                )
                continue
            elif process.computed_by == ComputedBy.simapro:
                impacts_simapro = process.impacts.model_dump(exclude={"ecs", "pef"})

                (computed_by, impacts_bw) = compute_impacts(
                    process.bw_activity,
                    main_method,
                    impacts_py,
                    IMPACTS_JSON,
                    process.source,
                    factors,
                    simapro=False,
                    brightway_fallback=True,
                )
                impacts_bw = impacts_bw.model_dump(exclude={"ecs", "pef"})
            else:
                impacts_bw = process.impacts.model_dump(exclude={"ecs", "pef"})

                (computed_by, impacts_simapro) = compute_impacts(
                    process.bw_activity,
                    main_method,
                    impacts_py,
                    IMPACTS_JSON,
                    process.source,
                    factors,
                    simapro=True,
                    brightway_fallback=False,
                )

                impacts_simapro = impacts_simapro.model_dump(exclude={"ecs", "pef"})

            plot_impacts(
                process_name=process.name,
                impacts_smp=impacts_simapro,
                impacts_bw=impacts_bw,
                folder=graph_folder,
                impacts_py=IMPACTS_JSON,
            )

    # Convert objects to dicts
    dumped_processes = [
        process.model_dump(by_alias=True, exclude={"bw_activity", "computed_by"})
        for process in processes
    ]

    if display_changes:
        display_changes_from_json(
            processes_impacts_path=impacts_relative_file_path,
            processes_corrected_impacts=dumped_processes,
            # Compare by default with the first output dir
            dir=dirs_to_export_to[0],
        )

    exported_files = export_processes_to_dirs(
        aggregated_relative_file_path,
        impacts_relative_file_path,
        dumped_processes,
        dirs_to_export_to,
    )

    format_json(" ".join(exported_files))

    logger.info("Export completed successfully.")
