#!/usr/bin/env python3

import multiprocessing
from multiprocessing import Pool
from typing import List, Optional
from ecobalyse_data import logging
from ecobalyse_data.typer import bw_databases_validation

import bw2calc
import bw2data
import orjson
import typer
from bw2data.project import projects
from typing_extensions import Annotated

from common import (
    calculate_aggregate,
    compute_normalization_factors,
    correct_process_impacts,
    fix_unit,
    with_subimpacts,
)
from common.export import IMPACTS_JSON, compute_brightway_impacts
from common.impacts import impacts as impacts_py
from common.impacts import main_method
from config import settings
from models.process import BwProcess, UnitEnum

normalization_factors = compute_normalization_factors(IMPACTS_JSON)

# Use rich for logging
logger = logging.get_logger(__name__)


# Init BW project
projects.set_current(settings.bw.project)
available_bw_databases = ", ".join(bw2data.databases)


def get_process_with_impacts(
    activity, main_method, impacts_py, impacts_json, database_name
) -> dict:
    impacts = None
    try:
        # Try to compute impacts using Brightway
        impacts = compute_brightway_impacts(activity, main_method, impacts_py)
        impacts = with_subimpacts(impacts)

        corrections = {
            k: v["correction"] for (k, v) in impacts_json.items() if "correction" in v
        }
        # This function directly mutate the impacts dicts
        correct_process_impacts(impacts, corrections)

        impacts["pef"] = calculate_aggregate(impacts, normalization_factors["pef"])
        impacts["ecs"] = calculate_aggregate(impacts, normalization_factors["ecs"])

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


def main(
    output_file: Annotated[
        typer.FileBinaryWrite,
        typer.Argument(help="The output json file."),
    ],
    # Take all the cores available minus one to avoid locking the system
    # If only one core is available, use it (that’s what the `or 1` is for)
    cpu_count: Annotated[
        Optional[int],
        typer.Option(
            help="The number of CPUs/cores to use for computation. Default to MAX-1."
        ),
    ] = multiprocessing.cpu_count() - 1 or 1,
    max: Annotated[
        int,
        typer.Option(
            help="Number of max processes to compute per DB. Useful for testing purpose. Negative value means all processes."
        ),
    ] = -1,
    db: Annotated[
        Optional[List[str]],
        typer.Option(
            callback=bw_databases_validation,
            help=f"Brightway databases you want to computate impacts for. Default to all. You can specify multiple `--db`.\n\nAvailable databases are: {available_bw_databases}.",
        ),
    ] = [],
):
    """
    Compute the detailed impacts for all the databases in the default Brightway project.

    You can specify the number of CPUs to be used for computation by specifying CPU_COUNT argument.
    """
    all_impacts = {}

    # Get specified dbs or default to all BW databases
    databases = db if db else bw2data.databases

    nb_processes = 0

    for database_name in databases:
        logger.info(f"-> Exploring DB '{database_name}'")

        db = bw2data.Database(database_name)

        logger.info(f"-> Total number of activities in db: {len(db)}")

        with Pool(cpu_count) as pool:
            activities_paramaters = []
            nb_activity = 0

            for activity in db:
                if "process" in activity.get("type") and (max < 0 or nb_activity < max):
                    activities_paramaters.append(
                        # Parameters of the `get_process_with_impacts` function
                        (activity, main_method, impacts_py, IMPACTS_JSON, database_name)
                    )
                    nb_activity += 1

            processes_with_impacts = pool.starmap(
                get_process_with_impacts, activities_paramaters
            )

            logger.info(
                f"-> Computed impacts for {len(processes_with_impacts)} processes in '{database_name}'"
            )

            all_impacts[database_name] = processes_with_impacts
            nb_processes += len(processes_with_impacts)

    db_names = ", ".join([f"'{db}'" for db in databases])

    logger.info(
        f"-> Finished computing impacts for {nb_processes} processes in {len(databases)} databases: {db_names}"
    )

    output_file.write(
        orjson.dumps(all_impacts, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS)
    )


if __name__ == "__main__":
    typer.run(main)
