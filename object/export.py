#!/usr/bin/env python
# coding: utf-8

"""Export des processes pour les objets"""

import argparse
import sys
from os.path import abspath, dirname, join

from bw2data.project import projects
from frozendict import frozendict
from loguru import logger

from common import brightway_patch as brightway_patch
from common import (
    with_aggregated_impacts,
)
from common.export import (
    IMPACTS_JSON,
    compute_impacts,
    display_changes,
    export_processes_to_dirs,
    format_json,
    generate_compare_graphs,
    load_json,
)
from common.impacts import impacts as impacts_py
from config import settings

PROJECT_ROOT_DIR = dirname(dirname(abspath(__file__)))
PROJECT_OBJECT_DIR = join(PROJECT_ROOT_DIR, settings.object.dirname)

dirs_to_export_to = [settings.output_dir]

if settings.local_export:
    dirs_to_export_to.append(join(PROJECT_ROOT_DIR, "public", "data"))

# Configuration
GRAPH_FOLDER = f"{PROJECT_ROOT_DIR}/object/impact_comparison"

# Configure logger
logger.remove()  # Remove default handler
logger.add(sys.stderr, format="{time} {level} {message}", level="INFO")


def create_process_list(activities):
    logger.info("Creating process list...")
    return frozendict({activity["id"]: activity for activity in activities})


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Also plot comparison graphs between Brightay and SimaPro",
    )
    args = parser.parse_args()
    logger.info("Starting export process")
    projects.set_current(settings.bw.project)

    # Load activities
    activities = load_json(join(PROJECT_OBJECT_DIR, settings.activities_file))

    # Create process list
    processes = create_process_list(activities)

    # processes with impacts, impacts_simapro and impacts_brightway
    processes_impacts = compute_impacts(
        processes, settings.bw.ecoinvent, impacts_py, IMPACTS_JSON, args.plot
    )

    # processes with impacts only
    processes_impacts = generate_compare_graphs(
        processes_impacts,
        impacts_py,
        GRAPH_FOLDER,
        settings.textile.dirname,
        args.plot,
    )
    processes_aggregated_impacts = with_aggregated_impacts(
        IMPACTS_JSON, processes_impacts
    )

    old_processes = load_json(
        join(
            settings.output_dir,
            settings.object.dirname,
            settings.processes_impacts_file,
        )
    )
    display_changes(
        "id",
        old_processes,
        processes_impacts,
        use_rich=True,
    )

    exported_files = export_processes_to_dirs(
        join(settings.object.dirname, settings.processes_aggregated_file),
        join(settings.object.dirname, settings.processes_impacts_file),
        processes_impacts,
        processes_aggregated_impacts,
        dirs_to_export_to,
    )

    format_json(" ".join(exported_files))

    logger.info("Export completed successfully.")
