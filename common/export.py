import json
import math
import os
import subprocess
from os.path import dirname
from typing import List

import matplotlib.pyplot
import numpy
from frozendict import deepfreeze
from rich.console import Console
from rich.table import Table

from config import settings
from ecobalyse_data.computation import compute_impacts
from ecobalyse_data.logging import logger
from models.process import ComputedBy, ProcessWithMetadata

from . import (
    FormatNumberJsonEncoder,
    get_normalization_weighting_factors,
    remove_detailed_impacts,
    sort_json,
)

PROJECT_ROOT_DIR = dirname(dirname(__file__))

with open(os.path.join(PROJECT_ROOT_DIR, settings.impacts_file)) as f:
    IMPACTS_JSON = deepfreeze(json.load(f))


def get_changes(old_impacts, new_impacts, process_name, only_impacts=[]):
    changes = []
    for trigram in new_impacts:
        if (
            only_impacts is not None
            and len(only_impacts) > 0
            and trigram not in only_impacts
        ):
            continue

        if old_impacts.get(trigram, {}):
            # Convert values to float before calculation
            old_value = float(old_impacts[trigram])
            new_value = float(new_impacts[trigram])

            if old_value == 0 and new_value == 0:
                percent_change = 0
            elif old_value == 0:
                percent_change = math.inf
            else:
                percent_change = 100 * (new_value - old_value) / old_value

            if abs(percent_change) > 0.1:
                changes.append(
                    {
                        "trg": trigram,
                        "name": process_name,
                        "%diff": percent_change,
                        "from": old_value,
                        "to": new_value,
                    }
                )

    return changes


def display_changes_table(changes, sort_by_key="%diff"):
    changes.sort(key=lambda c: (c["trg"] != "ecs", c["trg"] != "pef", c[sort_by_key]))

    table = Table(title="Review changes", show_header=True, show_footer=True)

    table.add_column("trg", "trg", style="cyan", no_wrap=True)
    table.add_column("name", "trg", style="magenta")
    table.add_column("%diff", "%diff")
    table.add_column("from", "from", style="green")
    table.add_column("to", "to", style="red")

    for change in changes:
        table.add_row(*[str(value) for value in change.values()])

    console = Console()
    console.print(table)


def display_changes(
    key,
    oldprocesses,
    processes,
    only_impacts=[],
):
    """Display a nice sorted table of impact changes to review
    key is the field to display (id for food, uuid for textile)"""
    old = {str(p[key]): p for p in oldprocesses if key in p}

    if type(processes) is list:
        # Be sure to convert to str if we have an UUID for the key
        processes = {str(p[key]): p for p in processes if key in p}

    review = False
    changes = []
    for id_, p in processes.items():
        # Skip if the id doesn't exist in old processes
        if id_ not in old:
            continue
        impact_changes = get_changes(
            old_impacts=old[id_]["impacts"],
            new_impacts=processes[id_]["impacts"],
            process_name=p["sourceId"],
            only_impacts=only_impacts,
        )

        if len(impact_changes) > 0:
            changes = changes + impact_changes
            review = True

    changes.sort(key=lambda c: abs(c["%diff"]))

    if review:
        display_changes_table(changes)


def plot_process_impacts(
    processes_with_metadata: List[ProcessWithMetadata],
    graph_folder: str,
    main_method,
    impacts_py,
    impacts_json,
    factors,
):
    """
    Plot impacts for a list of processes with metadata.

    Args:
        processes_with_metadata: List of ProcessWithMetadata objects to plot
        graph_folder: Directory to save the plots
        main_method: Main method for impact computation
        impacts_py: Impacts Python module
        impacts_json: Impacts JSON data
        factors: Normalization weighting factors
    """
    index = 1
    total = len(processes_with_metadata)

    for process in processes_with_metadata:
        logger.info(f"-> [{index}/{total}] Plotting impacts for '{process.source_id}'")
        index += 1
        os.makedirs(graph_folder, exist_ok=True)

        if process.computed_by == ComputedBy.hardcoded:
            logger.warning(
                f"-> The process '{process.source_id}' has harcoded impacts, it can't be plot, skipping."
            )
            continue
        elif process.source == "Ecobalyse":
            logger.warning(
                f"-> The process '{process.source_id}' has been constructed by 'Ecobalyse' and is not present in simapro, skipping."
            )
            continue
        elif process.computed_by == ComputedBy.simapro:
            impacts_simapro = process.impacts.model_dump(exclude={"ecs", "pef"})

            (computed_by, impacts_bw) = compute_impacts(
                process.bw_activity,
                main_method,
                impacts_py,
                impacts_json,
                factors,
                simapro=False,
            )
            impacts_bw = impacts_bw.model_dump(exclude={"ecs", "pef"})
        else:
            impacts_bw = process.impacts.model_dump(exclude={"ecs", "pef"})

            (computed_by, impacts_simapro) = compute_impacts(
                process.bw_activity,
                main_method,
                impacts_py,
                impacts_json,
                factors,
                simapro=True,
            )
            if not impacts_simapro:
                raise ValueError(
                    f"-> Unable to get Simapro impacts for '{process.source_id}', skipping."
                )

            impacts_simapro = impacts_simapro.model_dump(exclude={"ecs", "pef"})

        plot_impacts(
            process_name=process.source_id,
            impacts_smp=impacts_simapro,
            impacts_bw=impacts_bw,
            folder=graph_folder,
            impacts_py=impacts_json,
        )


def plot_impacts(process_name, impacts_smp, impacts_bw, folder, impacts_py):
    trigrams = [
        t
        for t in impacts_py.keys()
        if t in impacts_smp.keys() and t in impacts_bw.keys()
    ]
    factors = get_normalization_weighting_factors(impacts_py)

    simapro_values = [
        impacts_smp.get(t, 0) / factors["pef_normalizations"][t] for t in trigrams
    ]
    brightway_values = [
        impacts_bw.get(t, 0) / factors["pef_normalizations"][t] for t in trigrams
    ]

    x = numpy.arange(len(trigrams))
    width = 0.35

    fig, ax = matplotlib.pyplot.subplots(figsize=(12, 8))

    ax.bar(x - width / 2, simapro_values, width, label="SimaPro")
    ax.bar(x + width / 2, brightway_values, width, label="Brightway")

    ax.set_xlabel("Impact Categories")
    ax.set_ylabel("Impact Values (normalized, non weighted)")
    ax.set_title(f"Environmental Impacts for {process_name}")
    ax.set_xticks(x)
    ax.set_xticklabels(trigrams, rotation=90)
    ax.legend()

    matplotlib.pyplot.tight_layout()
    filepath = f"{folder}/{process_name.replace('/', '_')}.png"
    matplotlib.pyplot.savefig(filepath)
    logger.info(f"Saved impact comparison plot to {filepath}")
    matplotlib.pyplot.close()


def export_json(json_data, filename, sort=False):
    if sort:
        json_data = sort_json(json_data)

    logger.info(f"Exporting {filename}")
    json_string = json.dumps(
        json_data, indent=2, ensure_ascii=False, cls=FormatNumberJsonEncoder
    )
    with open(filename, "w", encoding="utf-8") as file:
        file.write(json_string)
        file.write("\n")  # Add a newline at the end of the file

    logger.info(f"Exported {len(json_data)} elements to {filename}")


def format_json(json_path):
    return subprocess.run(f"npm run fix:prettier {json_path}".split(" "))


def display_changes_from_json(
    processes_impacts_path,
    processes_corrected_impacts,
    dir,
):
    processes_impacts = os.path.join(dir, processes_impacts_path)

    if os.path.isfile(processes_impacts):
        # Load old processes for comparison
        oldprocesses = load_json(processes_impacts)

        # Display changes
        display_changes("id", oldprocesses, processes_corrected_impacts)


def export_processes_to_dirs(
    processes_aggregated_path,
    processes_impacts_path,
    processes_aggregated_impacts,
    dirs,
    extra_data=None,
    extra_path=None,
    merge=False,
    scopes=None,
):
    exported_files = []

    for dir in dirs:
        logger.info("")
        logger.info(f"-> Exporting to {dir}")
        processes_impacts_absolute_path = os.path.join(dir, processes_impacts_path)
        processes_aggregated_absolute_path = os.path.join(
            dir, processes_aggregated_path
        )

        if extra_data is not None and extra_path is not None:
            extra_file = os.path.join(dir, extra_path)
            export_json(extra_data, extra_file, sort=True)
            exported_files.append(extra_file)

        # Export results
        if type(processes_aggregated_impacts) is not list:
            to_export = list(processes_aggregated_impacts.values())
        else:
            to_export = processes_aggregated_impacts

        # If merge is true, we don't overwrite the existing file but merge the new processes with the existing ones
        if merge and scopes:
            if os.path.exists(processes_impacts_absolute_path):
                logger.info(
                    f"-> Merging with existing processes file {processes_impacts_absolute_path}"
                )
                with open(processes_impacts_absolute_path, "r") as f:
                    existing_processes = json.load(f)

                # delete all existing processes with a scope in scopes
                existing_processes = [
                    p
                    for p in existing_processes
                    if not any(s.value in p["scopes"] for s in scopes)
                ]

                # add the new processes to the existing processes
                to_export = existing_processes + to_export

        # Sort processes by id
        to_export.sort(key=lambda x: str(x["id"]))

        export_json(to_export, processes_impacts_absolute_path, sort=True)
        exported_files.append(processes_impacts_absolute_path)

        # Also update the aggregated file
        export_json(
            remove_detailed_impacts(to_export),
            processes_aggregated_absolute_path,
            sort=True,
        )
        exported_files.append(processes_aggregated_absolute_path)

    return exported_files


def load_json(filename):
    """
    Load JSON data from a file.
    """
    with open(filename, "r") as file:
        return json.load(file)
