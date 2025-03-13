#!/usr/bin/env python3


import uuid
from typing import List, Optional

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
from models.process import Impacts, Process

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
                eco_activity=activity,
                simapro=simapro,
            )
        )

    return processes


def compute_impacts(
    bw_activity,
    main_method,
    impacts_py,
    impacts_json,
    database_name,
    normalization_factors,
    simapro=False,
    brightway_fallback=True,
) -> Optional[Impacts]:
    impacts = None

    try:
        impacts = {}
        # Try to compute impacts using Simapro
        if simapro:
            logger.info(f"-> Getting impacts from Simapro for {bw_activity}")
            impacts = compute_simapro_impacts(bw_activity, main_method, impacts_py)

            # WARNING assume remote is in m3 or MJ (couldn't find unit from COM intf)
            if bw_activity.get("unit") == "kWh":
                impacts = {k: v * 3.6 for k, v in impacts.items()}
            elif bw_activity.get("unit") == "L":
                impacts = {k: v / 1000 for k, v in impacts.items()}

        if not simapro or (not impacts and brightway_fallback):
            logger.info(f"-> Getting impacts from BW for {bw_activity}")
            impacts = compute_brightway_impacts(bw_activity, main_method, impacts_py)

        impacts = with_subimpacts(impacts)

        corrections = {
            k: v["correction"] for (k, v) in impacts_json.items() if "correction" in v
        }
        # This function directly mutate the impacts dicts…
        correct_process_impacts(impacts, corrections)

        impacts["pef"] = calculate_aggregate("pef", impacts, normalization_factors)
        impacts["ecs"] = calculate_aggregate("ecs", impacts, normalization_factors)

    except bw2calc.errors.BW2CalcError as e:
        logger.error(f"-> Impossible to compute impacts in Brightway for {bw_activity}")
        logger.exception(e)

    return impacts


def compute_process_with_impacts(
    bw_activity,
    main_method,
    impacts_py,
    impacts_json,
    database_name,
    normalization_factors,
    eco_activity=dict(),
    simapro=False,
    brightway_fallback=True,
) -> Process:
    unit = fix_unit(bw_activity.get("unit"))

    bw_activity["unit"] = unit

    impacts = compute_impacts(
        bw_activity,
        main_method,
        impacts_py,
        impacts_json,
        database_name,
        normalization_factors,
        simapro=simapro,
        brightway_fallback=brightway_fallback,
    )

    return Process(
        categories=eco_activity.get("categories", bw_activity.get("categories", [])),
        comment=eco_activity.get("comment", bw_activity.get("comment", "")),
        density=eco_activity.get("density", bw_activity.get("density", 0)),
        # Default to bw_activity name if no display name is given
        displayName=eco_activity.get("displayName", bw_activity.get("name")),
        elecMJ=eco_activity.get("elecMJ", 0),
        heatMJ=eco_activity.get("heatMJ", 0),
        id=eco_activity.get(
            "id", uuid.uuid5(uuid.NAMESPACE_DNS, bw_activity.get("name"))
        ),
        impacts=impacts,
        name=bw_activity.get("name"),
        source=database_name,
        sourceId=bw_activity.get("Process identifier"),
        unit=bw_activity.get("unit"),
        waste=eco_activity.get("waste", bw_activity.get("waste", 0)),
    )
