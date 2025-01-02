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
    with_aggregated_impacts,
    with_corrected_impacts,
)
from common.export import (
    IMPACTS_JSON,
    compute_impacts,
    export_processes_to_dirs,
    load_json,
)
from common.impacts import impacts as impacts_py
from config import settings

PROJECT_ROOT_DIR = dirname(dirname(abspath(__file__)))
PROJECT_OBJECT_DIR = os.path.join(PROJECT_ROOT_DIR, settings.object.dirname)

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
    projects.set_current(settings.bw.project)
    # Load activities
    activities = load_json(os.path.join(PROJECT_OBJECT_DIR, settings.activities_file))

    # Create process list
    processes = create_process_list(activities)

    # Compute impacts
    processes_impacts = compute_impacts(processes, settings.bw.ecoinvent, impacts_py)

    # Apply corrections
    processes_corrected_impacts = with_corrected_impacts(
        IMPACTS_JSON, processes_impacts
    )
    processes_aggregated_impacts = with_aggregated_impacts(
        IMPACTS_JSON, processes_corrected_impacts
    )

    export_processes_to_dirs(
        os.path.join(settings.object.dirname, settings.processes_aggregated_file),
        os.path.join(settings.object.dirname, settings.processes_impacts_file),
        processes_corrected_impacts,
        processes_aggregated_impacts,
        dirs_to_export_to,
    )

    logger.info("Export completed successfully.")
