#!/usr/bin/env python3


import json

import bw2data
import typer
from bw2analyzer.utils import print_recursive_calculation
from bw2data.project import projects
from rich.pretty import pprint
from typing_extensions import Annotated

from common import (
    compute_normalization_factors,
)
from common.export import IMPACTS_JSON, display_changes, search
from common.impacts import impacts as impacts_py
from common.impacts import main_method
from config import settings
from ecobalyse_data import logging
from ecobalyse_data.computation import get_process_with_impacts
from ecobalyse_data.typer import bw_database_validation

# Use rich for logging
logger = logging.get_logger(__name__)


app = typer.Typer()


# Init BW project
projects.set_current(settings.bw.project)
available_bw_databases = ", ".join(bw2data.databases)


method = ("Environmental Footprint 3.1 (adapted) patch wtu", "Climate change")


@app.command()
def lcia_details(
    activity_name: Annotated[
        str,
        typer.Argument(help="Name of the activity (process) to look for."),
    ],
    database_name: Annotated[
        str,
        typer.Argument(
            callback=bw_database_validation,
            help=f"Brightway database containing the activity.\n\nAvailable databases are: {available_bw_databases}.",
        ),
    ],
):
    """
    Get detailed information about an LCIA
    """

    activity = search(database_name, activity_name)
    pprint(activity)

    print_recursive_calculation(activity, method, max_level=3)

    normalization_factors = compute_normalization_factors(IMPACTS_JSON)
    impacts = get_process_with_impacts(
        activity, main_method, impacts_py, database_name, normalization_factors
    )

    pprint(impacts)


@app.command()
def compare_processes(
    first_file: Annotated[
        typer.FileText,
        typer.Argument(help="The first json file."),
    ],
    second_file: Annotated[
        typer.FileText,
        typer.Argument(help="The second json file."),
    ],
):
    """
    Compare two `processes_impacts.json` files
    """

    first_processes = json.load(first_file)
    second_processes = json.load(second_file)
    display_changes(
        "id", first_processes, second_processes, impacts=["ecs"], uniq_by_name=True
    )


if __name__ == "__main__":
    app()
