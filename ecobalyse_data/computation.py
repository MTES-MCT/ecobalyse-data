#!/usr/bin/env python3


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
from ecobalyse_data import logging
from models.process import BwProcess, UnitEnum

# Use rich for logging
logger = logging.get_logger(__name__)


# Init BW project
projects.set_current(settings.bw.project)
available_bw_databases = ", ".join(bw2data.databases)


def compute_process_with_impacts(
    activity,
    main_method,
    impacts_py,
    impacts_json,
    database_name,
    normalization_factors,
    simapro=False,
) -> dict:
    impacts = None
    try:
        # Try to compute impacts using Brightway
        if simapro:
            impacts = compute_simapro_impacts(activity, main_method, impacts_py)
        else:
            impacts = compute_brightway_impacts(activity, main_method, impacts_py)

        impacts = with_subimpacts(impacts)

        corrections = {
            k: v["correction"] for (k, v) in impacts_json.items() if "correction" in v
        }
        # This function directly mutate the impacts dicts
        correct_process_impacts(impacts, corrections)

        impacts["pef"] = calculate_aggregate("pef", impacts, normalization_factors)
        impacts["ecs"] = calculate_aggregate("ecs", impacts, normalization_factors)

    except bw2calc.errors.BW2CalcError as e:
        logger.error(f"-> Impossible to compute impacts for {activity}")
        logger.exception(e)

    unit = fix_unit(activity.get("unit"))

    if unit not in UnitEnum.__members__.values():
        unit = None

    process = BwProcess(
        categories=activity.get("categories", []),
        comment=activity.get("comment", ""),
        impacts=impacts,
        name=activity.get("name"),
        source=database_name,
        sourceId=activity.get("Process identifier"),
        unit=unit,
    )

    return process.model_dump()
