#!/usr/bin/env python3

import multiprocessing
from multiprocessing import Pool
from typing import List, Optional

import bw2calc
import bw2data
import orjson
import typer
from bw2data.project import projects
from typing_extensions import Annotated

from common import (
    calculate_aggregate,
    correct_process_impacts,
    fix_unit,
    get_normalization_weighting_factors,
    with_subimpacts,
)
from common.export import IMPACTS_JSON, compute_brightway_impacts
from common.impacts import impacts as impacts_py
from common.impacts import main_method
from config import settings
from ecobalyse_data import logging
from models.process import BwProcess, UnitEnum

normalization_factors = get_normalization_weighting_factors(IMPACTS_JSON)

# Use rich for logging
logger = logging.get_logger(__name__)


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
            help="Number of max activity to compute the impacts for (per DB). Useful for testing purpose. Negative value means all activities."
        ),
    ] = -1,
    db: Annotated[
        Optional[List[str]],
        typer.Option(
            help="Brightway databases you want to computate impacts for. Default to all. You can specify multiple `--db`.",
        ),
    ] = [],
    project: Annotated[
        Optional[str],
        typer.Option(
            help=f"Brightway project name. Default to {settings.bw.project}.",
        ),
    ] = settings.bw.project,
    activity_name: Annotated[
        Optional[str],
        typer.Option(
            help=f"Brightway project name. Default to {settings.bw.project}.",
        ),
    ] = None,
    multiprocessing: Annotated[
        bool,
        typer.Option(help="Use multiprocessing for faster computation."),
    ] = True,
):
    """
    Compute the detailed impacts for all the databases in the default Brightway project.

    You can specify the number of CPUs to be used for computation by specifying CPU_COUNT argument.
    """

    # Init BW project
    projects.set_current(project)

    all_impacts = {}

    # Get specified dbs or default to all BW databases
    databases = db if db else bw2data.databases

    nb_processes = 0

    for database_name in databases:
        logger.info(f"-> Exploring DB '{database_name}'")

        db = bw2data.Database(database_name)

        with Pool(cpu_count) as pool:
            activities_parameters = []
            nb_activity = 0

            logger.info(
                f"-> Computing impacts for {len(db)} activities, using {cpu_count} cores, hold on, it will take a while…"
            )
            for activity in db:
                if "process" in activity.get("type") and (max < 0 or nb_activity < max):
                    if activity_name is None or (
                        activity_name is not None
                        and activity_name == activity.get("name")
                    ):
                        activities_parameters.append(
                            # Parameters of the `get_process_with_impacts` function
                            (
                                activity,
                                main_method,
                                impacts_py,
                                IMPACTS_JSON,
                                database_name,
                            )
                        )
                        nb_activity += 1

            processes_with_impacts = []
            if multiprocessing:
                processes_with_impacts = pool.starmap(
                    get_process_with_impacts, activities_parameters
                )
            else:
                for activity_parameters in activities_parameters:
                    processes_with_impacts.append(
                        get_process_with_impacts(*activity_parameters)
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
