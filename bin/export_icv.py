#!/usr/bin/env python3

import sys
from multiprocessing import Pool

import bw2calc
import bw2data
import orjson
from bw2data.project import projects
from loguru import logger

from common import (
    calculate_aggregate,
    compute_normalization_factors,
    fix_unit,
    with_subimpacts,
)
from common.export import IMPACTS_JSON, compute_brightway_impacts
from common.impacts import impacts as impacts_py
from common.impacts import main_method
from config import settings
from models.process import BwProcess, UnitEnum

normalization_factors = compute_normalization_factors(IMPACTS_JSON)

# Configure logger
logger.remove()  # Remove default handler
logger.add(sys.stderr, format="{time} {level} {message}", level="INFO")


def get_process_with_impacts(activity, main_method, impacts_py) -> dict:
    impacts = None
    try:
        # Try to compute impacts using Brightway
        impacts = compute_brightway_impacts(activity, main_method, impacts_py)
        impacts = with_subimpacts(impacts)

        impacts["pef"] = calculate_aggregate(impacts, normalization_factors["pef"])
        impacts["ecs"] = calculate_aggregate(impacts, normalization_factors["ecs"])

    except bw2calc.errors.BW2CalcError as e:
        logger.info(f"-> Impossible to compute impacts for {activity}")
        print(e)

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


if __name__ == "__main__":
    logger.info("-> Starting ICV export process")
    projects.set_current(settings.bw.project)

    all_impacts = {}
    for database_name in bw2data.databases:
        logger.info(f"-> Exploring DB {database_name}")
        db = bw2data.Database(database_name)

        logger.info(f"-> Size {len(db)}")

        with Pool() as pool:
            db_impacts = pool.starmap(
                get_process_with_impacts,
                [
                    (activity, main_method, impacts_py)
                    for activity in db
                    if "process" in activity.get("type")
                ],
            )

            logger.info(f"-> Got {len(db_impacts)} results for {database_name}")
            all_impacts[database_name] = db_impacts

    logger.info("-> Finished computing impacts")

    with open("bw_impacts.json", "wb") as fp:
        fp.write(
            orjson.dumps(all_impacts, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS)
        )
