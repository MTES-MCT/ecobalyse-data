#!/usr/bin/env python3

import json
import logging
import multiprocessing
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
from models.process import Scope

app = typer.Typer()


PROJECT_ROOT_DIR = os.path.dirname(os.path.dirname(__file__))


class MetadataScope(str, Enum):
    food = Scope.food.value
    textile = Scope.textile.value


@app.command()
def metadata(
    scopes: Annotated[
        Optional[List[MetadataScope]],
        typer.Option(help="The scope to export. If not specified, exports all scopes."),
    ] = [MetadataScope.textile, MetadataScope.food],
    verbose: bool = typer.Option(False, "--verbose", "-v"),
    cpu_count: Annotated[
        Optional[int],
        typer.Option(
            help="The number of CPUs/cores to use for computation. Default to MAX-1."
        ),
    ] = multiprocessing.cpu_count() - 1 or 1,
):
    """
    Export metadata files (materials.json, ingredients.json, …)
    """
    if verbose:
        logger.setLevel(logging.DEBUG)

    dirs_to_export_to = [settings.output_dir]

    if settings.local_export:
        dirs_to_export_to.append(os.path.join(get_absolute_path("."), "public", "data"))

    activities_path = get_absolute_path("activities.json")
    logger.debug(f"-> Loading activities file {activities_path}")

    with open(activities_path, "r") as file:
        activities = json.load(file)

    for s in scopes:
        scope_dirname = settings.scopes.get(s.value).dirname
        if s == MetadataScope.textile:
            # Export textile materials
            activities_textile_materials = [
                a
                for a in activities
                if scope_dirname in a.get("scopes", [])
                and "textile_material" in a.get("categories", [])
            ]

            export_textile.activities_to_materials_json(
                activities_textile_materials,
                materials_paths=[
                    os.path.join(
                        get_absolute_path(dir), scope_dirname, "materials.json"
                    )
                    for dir in dirs_to_export_to
                ],
            )

        elif s == MetadataScope.food:
            # Export food ingredients
            activities_food_ingredients = [
                a
                for a in activities
                if scope_dirname in a.get("scopes", [])
                and "ingredient" in a.get("categories", [])
            ]

            export_food.activities_to_ingredients_json(
                activities_food_ingredients,
                ingredients_paths=[
                    os.path.join(
                        get_absolute_path(dir), scope_dirname, "ingredients.json"
                    )
                    for dir in dirs_to_export_to
                ],
                ecosystemic_factors_path=os.path.join(
                    get_absolute_path(
                        scope_dirname,
                        base_path=os.path.join(
                            PROJECT_ROOT_DIR, settings.get("BASE_PATH", "")
                        ),
                    ),
                    settings.scopes.food.ecosystemic_factors_file,
                ),
                feed_file_path=os.path.join(
                    get_absolute_path(
                        scope_dirname,
                        base_path=os.path.join(
                            PROJECT_ROOT_DIR, settings.get("BASE_PATH", "")
                        ),
                    ),
                    settings.scopes.food.feed_file,
                ),
                ugb_file_path=os.path.join(
                    get_absolute_path(
                        scope_dirname,
                        base_path=os.path.join(
                            PROJECT_ROOT_DIR, settings.get("BASE_PATH", "")
                        ),
                    ),
                    settings.scopes.food.ugb_file,
                ),
                cpu_count=cpu_count,
            )


@app.command()
def processes(
    scopes: Annotated[
        Optional[List[Scope]],
        typer.Option(help="The scope to export. If not specified, exports all scopes."),
    ] = None,
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
    ] = False,
    # Take all the cores available minus one to avoid locking the system
    # If only one core is available, use it (that’s what the `or 1` is for)
    cpu_count: Annotated[
        Optional[int],
        typer.Option(
            help="The number of CPUs/cores to use for computation. Default to MAX-1."
        ),
    ] = multiprocessing.cpu_count() - 1 or 1,
    plot: bool = typer.Option(False, "--plot", "-p"),
    merge: bool = typer.Option(False, "--merge", "-m"),
    verbose: bool = typer.Option(False, "--verbose", "-v"),
):
    """
    Export processes. If scope is specified, only exports processes for that scope.
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

    activities_path = get_absolute_path("activities.json")
    logger.debug(f"-> Loading activities file {activities_path}")

    with open(activities_path, "r") as file:
        activities = json.load(file)

    # Filter activities by scope if specified
    if scopes:
        activities = [
            a for a in activities if any(s.value in a.get("scopes", []) for s in scopes)
        ]
        logger.info(
            f"-> Filtered activities to scopes: {scopes}, activities remaining: {len(activities)}"
        )

    export_process.activities_to_processes(
        activities=activities,
        aggregated_relative_file_path=settings.processes_aggregated_file,
        impacts_relative_file_path=settings.processes_impacts_file,
        dirs_to_export_to=dirs_to_export_to,
        plot=should_plot,
        graph_folder=graph_folder,
        display_changes=display_changes,
        simapro=simapro,
        merge=merge,
        scopes=scopes,
        cpu_count=cpu_count,
    )


if __name__ == "__main__":
    projects.set_current(settings.bw.project)
    app()
