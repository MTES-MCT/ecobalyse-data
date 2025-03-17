#!/usr/bin/env python3


import logging
import os

import typer
from bw2data.project import projects

from config import get_absolute_path, settings
from ecobalyse_data import export
from ecobalyse_data.logging import logger

app = typer.Typer()


@app.command()
def food():
    """
    Export food
    """

    pass


@app.command()
def textile(
    plot: bool = typer.Option(False, "--plot", "-p"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """
    Export textile
    """

    if verbose:
        logger.setLevel(logging.DEBUG)

    logger.info("INFO")
    logger.debug("DEBUG")

    dirs_to_export_to = [settings.output_dir]

    if settings.local_export:
        dirs_to_export_to.append(os.path.join(get_absolute_path("."), "public", "data"))

    export.run(
        activities_path=os.path.join(
            get_absolute_path(settings.textile.dirname), "activities.json"
        ),
        aggregated_relative_file_path=os.path.join(
            settings.textile.dirname, settings.processes_aggregated_file
        ),
        impacts_relative_file_path=os.path.join(
            settings.textile.dirname, settings.processes_aggregated_file
        ),
        dirs_to_export_to=dirs_to_export_to,
        verbose=verbose,
        plot=plot,
    )


@app.command()
def object(
    plot: bool = typer.Option(False, "--plot", "-p"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """
    Export object
    """

    if verbose:
        logger.setLevel(logging.DEBUG)

    logger.info("INFO")
    logger.debug("DEBUG")

    dirs_to_export_to = [settings.output_dir]

    if settings.local_export:
        dirs_to_export_to.append(os.path.join(get_absolute_path("."), "public", "data"))

    export.run(
        activities_path=os.path.join(
            get_absolute_path(settings.object.dirname), "activities.json"
        ),
        aggregated_relative_file_path=os.path.join(
            settings.object.dirname, settings.processes_aggregated_file
        ),
        impacts_relative_file_path=os.path.join(
            settings.object.dirname, settings.processes_aggregated_file
        ),
        dirs_to_export_to=dirs_to_export_to,
        verbose=verbose,
        plot=plot,
    )


if __name__ == "__main__":
    projects.set_current(settings.bw.project)
    app()
