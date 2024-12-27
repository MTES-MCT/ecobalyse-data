#!/usr/bin/env python
# coding: utf-8

"""Export des processes pour les objets"""

import os
import sys
from os.path import abspath, dirname

from bw2data.project import projects
from frozendict import frozendict
from loguru import logger

from common import brightway_patch as brightway_patch
from common import (
    order_json,
    remove_detailed_impacts,
    with_aggregated_impacts,
    with_corrected_impacts,
)
from common.export import (
    IMPACTS_JSON,
    compute_impacts,
    display_changes,
    export_json,
    load_json,
)
from common.impacts import impacts as impacts_py
from config import settings

PROJECT_ROOT_DIR = dirname(dirname(abspath(__file__)))

dirs_to_export_to = [settings.output_dir]

if settings.local_export:
    dirs_to_export_to.append(os.path.join(PROJECT_ROOT_DIR, "public", "data"))

# Configure logger
logger.remove()  # Remove default handler
logger.add(sys.stderr, format="{time} {level} {message}", level="INFO")


def create_process_list(activities):
    logger.info("Creating process list...")
    return frozendict({activity["id"]: activity for activity in activities})


if __name__ == "__main__":
    logger.info("Starting export process")
    projects.set_current(settings.bw_project)
    # Load activities
    activities = load_json(
        os.path.join(PROJECT_ROOT_DIR, settings.object.activities_file)
    )

    # Create process list
    processes = create_process_list(activities)

    # Compute impacts
    processes_impacts = compute_impacts(processes, settings.bw_ecoinvent, impacts_py)

    # Apply corrections
    processes_corrected_impacts = with_corrected_impacts(
        IMPACTS_JSON, processes_impacts
    )
    processes_aggregated_impacts = with_aggregated_impacts(
        IMPACTS_JSON, processes_corrected_impacts
    )

    for dir in dirs_to_export_to:
        processes_impacts = os.path.join(dir, settings.object.processes_impacts)
        processes_aggregated = os.path.join(dir, settings.object.processes_aggregated)

        if os.path.isfile(processes_impacts):
            # Load old processes for comparison
            oldprocesses = load_json(processes_impacts)

            # Display changes
            display_changes("id", oldprocesses, processes_corrected_impacts)

        # Export results
        export_json(
            order_json(list(processes_aggregated_impacts.values())), processes_impacts
        )
        export_json(
            order_json(
                remove_detailed_impacts(list(processes_aggregated_impacts.values()))
            ),
            processes_aggregated,
        )

    logger.info("Export completed successfully.")
