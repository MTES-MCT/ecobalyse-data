#!/usr/bin/env python3


import json

import typer
from typing_extensions import Annotated

from common.export import display_changes
from ecobalyse_data import logging

# Use rich for logging
logger = logging.get_logger(__name__)


def main(
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
    Compare two `processes_impacts.json` files.
    """

    first_processes = json.load(first_file)
    second_processes = json.load(second_file)
    display_changes(
        "id", first_processes, second_processes, impacts=["ecs"], uniq_by_name=True
    )


if __name__ == "__main__":
    typer.run(main)
