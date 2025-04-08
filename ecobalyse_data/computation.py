#!/usr/bin/env python3


import json
import urllib.parse
import uuid
from typing import List, Optional

import bw2calc
import bw2data
import requests
from bw2data.project import projects

from common import (
    bytrigram,
    calculate_aggregate,
    correct_process_impacts,
    fix_unit,
    spproject,
    with_subimpacts,
)
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
        factors,
        simapro=simapro,
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
                f"This activity was not found in Brightway: {activity['displayName']}. Searched '{search_term}' in database '{db_name}'."
            )

        (computed_by, impacts) = compute_impacts(
            bw_activity,
            main_method,
            impacts_py,
            impacts_json,
            factors,
            simapro=simapro,
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
    activities: List[dict], main_method, impacts_py, impacts_json, factors, simapro=True
) -> List[Process]:
    processes: List[Process] = []

    index = 1
    total = len(activities)

    for activity in activities:
        logger.info(
            f"-> [{index}/{total}] Getting impacts for '{activity.get('displayName')}'"
        )
        index += 1

        process = compute_process_for_activity(
            activity,
            main_method,
            impacts_py,
            impacts_json,
            factors,
            simapro=False if activity["source"] == "Ecobalyse" else simapro,
        )

        if process:
            processes.append(process)

    return processes


def compute_impacts(
    bw_activity,
    main_method,
    impacts_py,
    impacts_json,
    normalization_factors,
    simapro=False,
    with_aggregated=True,
) -> tuple[str, Optional[Impacts]]:
    impacts = None

    computed_by = None
    try:
        impacts = {}

        # Try to compute impacts using Simapro
        if simapro:
            logger.info(f"-> Getting impacts from Simapro for {bw_activity}")
            impacts = compute_simapro_impacts(bw_activity, main_method, impacts_py)

            if not impacts:
                logger.error(
                    f"-> Impacts retrieval from Simapro failed for {bw_activity}"
                )

            unit = fix_unit(bw_activity.get("unit"))

            # WARNING assume remote is in m3 or MJ (couldn't find unit from COM intf)
            if unit == "kWh":
                impacts = {k: v * 3.6 for k, v in impacts.items()}
            elif unit == "L":
                impacts = {k: v / 1000 for k, v in impacts.items()}

            computed_by = ComputedBy.simapro
        else:
            logger.info(f"-> Getting impacts from BW for {bw_activity}")
            impacts = compute_brightway_impacts(bw_activity, main_method, impacts_py)

            computed_by = ComputedBy.brightway

        if not impacts:
            return (computed_by, None)

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


def compute_brightway_impacts(activity, method, impacts_py):
    results = dict()
    lca = bw2calc.LCA({activity: 1})
    lca.lci()
    for key, method in impacts_py.items():
        lca.switch_method(method)
        lca.lcia()
        results[key] = float("{:.10g}".format(lca.score))
        logger.debug(f"{activity}  {key}: {lca.score}")

    return results


def compute_simapro_impacts(activity, method, impacts_py):
    project, library = spproject(activity)
    name = (
        activity["name"]
        if project != "WFLDB"
        # TODO this should probably done through disabling a strategy
        else f"{activity['name']}/{activity['location']} U"
    )
    strprocess = urllib.parse.quote(name, encoding=None, errors=None)
    project = urllib.parse.quote(project, encoding=None, errors=None)
    library = urllib.parse.quote(library, encoding=None, errors=None)
    method = urllib.parse.quote(method, encoding=None, errors=None)
    api_request = f"http://simapro.ecobalyse.fr:8000/impact?process={strprocess}&project={project}&library={library}&method={method}"
    logger.debug(f"SimaPro API request: {api_request}")

    try:
        response = requests.get(api_request)
    except requests.exceptions.ConnectTimeout:
        logger.warning("SimaPro did not answer! Is it started?")
        return dict()

    try:
        json_content = json.loads(response.content)

        # If Simapro doesn't return a dict, it's most likely an error
        # (project not found) Don't do anything and return None,
        # BW will be used as a replacement
        if isinstance(json_content, dict):
            return bytrigram(impacts_py, json_content)
    except ValueError:
        pass

    return dict()


def activity_to_process_with_impacts(
    eco_activity, impacts, computed_by: ComputedBy, bw_activity={}
):
    unit = fix_unit(bw_activity.get("unit"))

    bw_activity["unit"] = unit

    # Some hardcoded activities don't have a name
    name = bw_activity.get(
        "name", eco_activity.get("name", eco_activity.get("displayName"))
    )

    # If we don’t have a real bw_activity instance but a dict instead, don’t try to get
    # comments from the database
    if isinstance(bw_activity, dict):
        comment = eco_activity.get("comment", bw_activity.get("comment", ""))
    else:
        comment = eco_activity.get("comment")

        # If we have no comment in the activity field, try to search for it in the bw database
        if not comment:
            prod = list(bw_activity.production())
            if prod:
                comment = prod[0].get("comment")

            # If we still have no comment, get the one from the bw_activity or ""
            if not comment:
                comment = bw_activity.get("comment", "")

    return Process(
        bw_activity=bw_activity,
        categories=eco_activity.get("categories", bw_activity.get("categories", [])),
        comment=comment,
        computed_by=computed_by,
        density=eco_activity.get("density", bw_activity.get("density", 0)),
        # Default to bw_activity name if no display name is given
        display_name=eco_activity.get("displayName", bw_activity.get("name")),
        elec_mj=eco_activity.get("elecMJ", 0),
        heat_mj=eco_activity.get("heatMJ", 0),
        id=eco_activity.get(
            "id",
            uuid.uuid5(uuid.NAMESPACE_DNS, name),
        ),
        impacts=impacts,
        name=name,
        source=eco_activity.get("source"),
        source_id=eco_activity.get(
            "sourceId", bw_activity.get("Process identifier", eco_activity.get("id"))
        ),
        unit=eco_activity.get("unit", bw_activity.get("unit")),
        waste=eco_activity.get("waste", bw_activity.get("waste", 0)),
    )
