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
    with_subimpacts,
)
from common.export import compute_brightway_impacts, compute_simapro_impacts
from config import settings
from ecobalyse_data.bw.search import cached_search_one
from ecobalyse_data.logging import logger
from models.process import ComputedBy, Impacts, Process

# Init BW project
projects.set_current(settings.bw.project)
available_bw_databases = ", ".join(bw2data.databases)


def compute_process_for_bw_activity(
    bw_activity,
    main_method,
    impacts_py,
    impacts_json,
    factors,
    simapro=True,
) -> Optional[Process]:
    computed_by = None
    impacts = {}

    (computed_by, impacts) = compute_impacts(
        bw_activity,
        main_method,
        impacts_py,
        impacts_json,
        bw_activity.get("database"),
        factors,
        simapro=simapro,
        brightway_fallback=True,
    )

    process = activity_to_process_with_impacts(
        eco_activity={"source": bw_activity.get("database")},
        impacts=impacts,
        computed_by=computed_by,
        bw_activity=bw_activity,
    )

    return process


def compute_process_for_activity(
    activity,
    main_method,
    impacts_py,
    impacts_json,
    factors,
    simapro=True,
) -> Optional[Process]:
    computed_by = None
    impacts = activity.get("impacts")
    bw_activity = {}

    # Impacts are not hardcoded, we should compute them
    if not impacts:
        # use search field first, then fallback to name and then to displayName
        search_term = activity.get(
            "search", activity.get("name", activity.get("displayName"))
        )

        db_name = activity.get("source")

        if search_term is None:
            logger.error(
                f"-> Unable te get search_term for activity {activity}, skipping."
            )
            logger.error(activity)
            return

        bw_activity = cached_search_one(db_name, search_term)

        if not bw_activity:
            raise Exception(
                f"This activity was not found in Brightway: {activity['name']}. Searched '{search_term}' in database '{db_name}'."
            )

        if activity["source"] == "Ecobalyse":
            simapro = False
        else:
            simapro = True

        (computed_by, impacts) = compute_impacts(
            bw_activity,
            main_method,
            impacts_py,
            impacts_json,
            db_name,
            factors,
            simapro=simapro,
            brightway_fallback=True,
        )
    else:
        # Impacts are harcoded, we just need to compute the agregated impacts
        impacts["pef"] = calculate_aggregate("pef", impacts, factors)
        impacts["ecs"] = calculate_aggregate("ecs", impacts, factors)
        computed_by = ComputedBy.hardcoded

    process = activity_to_process_with_impacts(
        eco_activity=activity,
        impacts=impacts,
        computed_by=computed_by,
        bw_activity=bw_activity,
    )

    return process


def compute_processes_for_activities(
    activities: List[dict],
    main_method,
    impacts_py,
    impacts_json,
    factors,
    simapro=True,
) -> List[Process]:
    processes: List[Process] = []

    for activity in activities:
        process = compute_process_for_activity(
            activity,
            main_method,
            impacts_py,
            impacts_json,
            factors,
            simapro=True,
        )

        if process:
            processes.append(process)

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
    with_aggregated=True,
) -> tuple[str, Impacts]:
    impacts = None

    computed_by = None
    try:
        impacts = {}
        # Try to compute impacts using Simapro
        if simapro:
            logger.info(f"-> Getting impacts from Simapro for {bw_activity}")
            impacts = compute_simapro_impacts(bw_activity, main_method, impacts_py)

            unit = fix_unit(bw_activity.get("unit"))

            # WARNING assume remote is in m3 or MJ (couldn't find unit from COM intf)
            if unit == "kWh":
                impacts = {k: v * 3.6 for k, v in impacts.items()}
            elif unit == "L":
                impacts = {k: v / 1000 for k, v in impacts.items()}

            computed_by = ComputedBy.simapro

        if not simapro or (not impacts and brightway_fallback):
            logger.info(f"-> Getting impacts from BW for {bw_activity}")
            impacts = compute_brightway_impacts(bw_activity, main_method, impacts_py)

            computed_by = ComputedBy.brightway

        impacts = with_subimpacts(impacts)

        corrections = {
            k: v["correction"] for (k, v) in impacts_json.items() if "correction" in v
        }
        # This function directly mutate the impacts dicts…
        correct_process_impacts(impacts, corrections)

        if with_aggregated:
            impacts["pef"] = calculate_aggregate("pef", impacts, normalization_factors)
            impacts["ecs"] = calculate_aggregate("ecs", impacts, normalization_factors)

    except bw2calc.errors.BW2CalcError as e:
        logger.error(f"-> Impossible to compute impacts in Brightway for {bw_activity}")
        logger.exception(e)

    return (computed_by, Impacts(**impacts))


def activity_to_process_with_impacts(
    eco_activity, impacts, computed_by: ComputedBy, bw_activity={}
):
    unit = fix_unit(bw_activity.get("unit"))

    bw_activity["unit"] = unit

    # Some hardcoded activities don't have a name
    name = bw_activity.get(
        "name", eco_activity.get("name", eco_activity.get("displayName"))
    )

    return Process(
        bw_activity=bw_activity,
        categories=eco_activity.get("categories", bw_activity.get("categories", [])),
        comment=eco_activity.get("comment", bw_activity.get("comment", "")),
        computed_by=computed_by,
        density=eco_activity.get("density", bw_activity.get("density", 0)),
        # Default to bw_activity name if no display name is given
        displayName=eco_activity.get("displayName", bw_activity.get("name")),
        elecMJ=eco_activity.get("elecMJ", 0),
        heatMJ=eco_activity.get("heatMJ", 0),
        id=eco_activity.get(
            "id",
            uuid.uuid5(uuid.NAMESPACE_DNS, name),
        ),
        impacts=impacts,
        name=name,
        source=eco_activity.get("source"),
        sourceId=eco_activity.get("sourceId", bw_activity.get("Process identifier")),
        unit=eco_activity.get("unit", bw_activity.get("unit")),
        waste=eco_activity.get("waste", bw_activity.get("waste", 0)),
    )
