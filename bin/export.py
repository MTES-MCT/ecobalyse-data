#!/usr/bin/env python3


import logging
import os
from enum import Enum
from typing import List

import typer
from bw2data.project import projects
from typing_extensions import Annotated

from config import get_absolute_path, settings
from ecobalyse_data import export
from ecobalyse_data.logging import logger

app = typer.Typer()


class Domain(str, Enum):
    food = "food"
    object = "object"
    textile = "textile"


@app.command()
def processes(
    domain: Annotated[
        List[Domain],
        typer.Option(
            help="The domain you want to export processes for. By default, export everything."
        ),
    ] = [d.value for d in Domain],
    plot: bool = typer.Option(False, "--plot", "-p"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """
    Export processes
    """

    if verbose:
        logger.setLevel(logging.DEBUG)

    dirs_to_export_to = [settings.output_dir]

    if settings.local_export:
        dirs_to_export_to.append(os.path.join(get_absolute_path("."), "public", "data"))

    for d in domain:
        dirname = settings.get(d.value).dirname
        export.run(
            activities_path=os.path.join(get_absolute_path(dirname), "activities.json"),
            aggregated_relative_file_path=os.path.join(
                dirname, settings.processes_aggregated_file
            ),
            impacts_relative_file_path=os.path.join(
                dirname, settings.processes_impacts_file
            ),
            dirs_to_export_to=dirs_to_export_to,
            verbose=verbose,
            plot=plot,
        )


if __name__ == "__main__":
    projects.set_current(settings.bw.project)
    app()
