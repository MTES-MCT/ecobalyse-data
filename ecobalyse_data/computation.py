#!/usr/bin/env python3


from typing import List

import bw2calc
import bw2data
from bw2data.project import projects

from common import (
    calculate_aggregate,
    correct_process_impacts,
    fix_unit,
    get_normalization_weighting_factors,
    with_subimpacts,
)
from common.export import compute_brightway_impacts, compute_simapro_impacts
from config import settings
from ecobalyse_data.bw.search import cached_search_one
from ecobalyse_data.logging import logger
from models.process import Process, UnitEnum

# Init BW project
projects.set_current(settings.bw.project)
available_bw_databases = ", ".join(bw2data.databases)


def compute_processes_for_activities(
    activities: List[dict],
    main_method,
    impacts_py,
    impacts_json,
    simapro=True,
) -> List[Process]:
    factors = get_normalization_weighting_factors(impacts_json)

    processes: List[Process] = []

    for activity in activities:
        search_term = activity.get("search", activity["name"])
        db_name = activity.get("source")

        bw_activity = cached_search_one(db_name, search_term)

        if not bw_activity:
            raise Exception(
                f"This activity was not found in Brightway: {activity['name']}. Searched '{search_term}' in database '{db_name}'."
            )

        if activity["source"] == "Ecobalyse":
            simapro = False
        else:
            simapro = True

        processes.append(
            compute_process_with_impacts(
                bw_activity,
                main_method,
                impacts_py,
                impacts_json,
                db_name,
                factors,
                display_name=activity.get("displayName"),
                simapro=simapro,
            )
        )

    return processes


def compute_process_with_impacts(
    bw_activity,
    main_method,
    impacts_py,
    impacts_json,
    database_name,
    normalization_factors,
    display_name=None,
    simapro=False,
    brightway_fallback=True,
) -> Process:
    impacts = None

    unit = fix_unit(bw_activity.get("unit"))

    if unit not in UnitEnum.__members__.values():
        unit = None

    try:
        impacts = {}
        # Try to compute impacts using Simapro
        if simapro:
            logger.info(f"-> Getting impacts from Simapro for {bw_activity}")
            impacts = compute_simapro_impacts(bw_activity, main_method, impacts_py)

            # WARNING assume remote is in m3 or MJ (couldn't find unit from COM intf)
            if unit == "kWh":
                impacts = {k: v * 3.6 for k, v in impacts.items()}
            elif unit == "L":
                impacts = {k: v / 1000 for k, v in impacts.items()}

        if not simapro or (not impacts and brightway_fallback):
            logger.info(f"-> Getting impacts from BW for {bw_activity}")
            impacts = compute_brightway_impacts(bw_activity, main_method, impacts_py)

        impacts = with_subimpacts(impacts)

        corrections = {
            k: v["correction"] for (k, v) in impacts_json.items() if "correction" in v
        }
        # This function directly mutate the impacts dicts
        correct_process_impacts(impacts, corrections)

        impacts["pef"] = calculate_aggregate("pef", impacts, normalization_factors)
        impacts["ecs"] = calculate_aggregate("ecs", impacts, normalization_factors)

    except bw2calc.errors.BW2CalcError as e:
        logger.error(f"-> Impossible to compute impacts in Brightway for {bw_activity}")
        logger.exception(e)

    return Process(
        categories=bw_activity.get("categories", []),
        comment=bw_activity.get("comment", ""),
        density=bw_activity.get("density", 0),
        # Default to bw_activity name if no display name is given
        displayName=display_name if display_name else bw_activity.get("name"),
        impacts=impacts,
        name=bw_activity.get("name"),
        source=database_name,
        sourceId=bw_activity.get("Process identifier"),
        unit=unit,
        waste=bw_activity.get("waste", 0),
    )
