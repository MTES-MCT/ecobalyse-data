#!/usr/bin/env python3


import json
import logging
import os
from enum import Enum
from pathlib import Path
from typing import List, Optional

import typer
from bw2data.project import projects
from typing_extensions import Annotated

from config import get_absolute_path, settings
from ecobalyse_data.export import food as export_food
from ecobalyse_data.export import process as export_process
from ecobalyse_data.export import textile as export_textile
from ecobalyse_data.logging import logger

app = typer.Typer()


PROJECT_ROOT_DIR = os.path.dirname(os.path.dirname(__file__))


class Domain(str, Enum):
    food = "food"
    object = "object"
    textile = "textile"


class MetadataDomain(str, Enum):
    food = Domain.food.value
    textile = Domain.textile.value


@app.command()
def metadata(
    domain: Annotated[
        List[MetadataDomain],
        typer.Option(
            help="The domain you want to create metadata for. By default, export everything.",
        ),
    ] = [MetadataDomain.textile],
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """
    Export metadata files (materials.json, ingredients.json, …)
    """
    if verbose:
        logger.setLevel(logging.DEBUG)

    dirs_to_export_to = [settings.output_dir]

    if settings.local_export:
        dirs_to_export_to.append(os.path.join(get_absolute_path("."), "public", "data"))

    for d in domain:
        domain_dirname = settings.domains.get(d.value).dirname
        if d == MetadataDomain.textile:
            export_textile.activities_to_materials_json(
                activities_path=os.path.join(
                    get_absolute_path(domain_dirname), "activities.json"
                ),
                materials_paths=[
                    os.path.join(
                        get_absolute_path(dir), domain_dirname, "materials.json"
                    )
                    for dir in dirs_to_export_to
                ],
            )
        elif d == MetadataDomain.food:
            export_food.activities_to_ingredients_json(
                activities_path=os.path.join(
                    get_absolute_path(domain_dirname), "activities.json"
                ),
                ingredients_paths=[
                    os.path.join(
                        get_absolute_path(dir), domain_dirname, "ingredients.json"
                    )
                    for dir in dirs_to_export_to
                ],
                ecosystemic_factors_path=os.path.join(
                    get_absolute_path(domain_dirname, base_path=PROJECT_ROOT_DIR),
                    settings.domains.food.ecosystemic_factors_file,
                ),
                feed_file_path=os.path.join(
                    get_absolute_path(domain_dirname, base_path=PROJECT_ROOT_DIR),
                    settings.domains.food.feed_file,
                ),
                ugb_file_path=os.path.join(
                    get_absolute_path(domain_dirname, base_path=PROJECT_ROOT_DIR),
                    settings.domains.food.ugb_file,
                ),
            )


@app.command()
def processes(
    domain: Annotated[
        List[Domain],
        typer.Option(
            help="The domain you want to export processes for. By default, export everything."
        ),
    ] = [d.value for d in Domain],
    graph_folder: Annotated[
        Optional[Path],
        typer.Option(help="The graph output path."),
    ] = os.path.join(get_absolute_path("."), "graphs"),
    display_changes: Annotated[
        bool,
        typer.Option(help="Display changes with old processes."),
    ] = True,
    simapro: Annotated[
        bool,
        typer.Option(help="Use simapro"),
    ] = True,
    plot: bool = typer.Option(False, "--plot", "-p"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """
    Export processes
    """

    if verbose:
        logger.setLevel(logging.DEBUG)

    dirs_to_export_to = [settings.output_dir]

    should_plot = settings.plot_export

    # Override config if cli parameter is present
    if plot:
        should_plot = True

    if settings.local_export:
        dirs_to_export_to.append(os.path.join(get_absolute_path("."), "public", "data"))

    for d in domain:
        dirname = settings.domains.get(d.value).dirname

        activities_path = os.path.join(get_absolute_path(dirname), "activities.json")

        logger.debug(f"-> Loading activities file {activities_path}")

        with open(activities_path, "r") as file:
            activities = json.load(file)

            export_process.activities_to_processes(
                activities=activities,
                aggregated_relative_file_path=os.path.join(
                    dirname, settings.processes_aggregated_file
                ),
                impacts_relative_file_path=os.path.join(
                    dirname, settings.processes_impacts_file
                ),
                dirs_to_export_to=dirs_to_export_to,
                plot=should_plot,
                graph_folder=os.path.join(graph_folder, dirname),
                display_changes=display_changes,
                simapro=simapro,
            )


if __name__ == "__main__":
    projects.set_current(settings.bw.project)
    app()
