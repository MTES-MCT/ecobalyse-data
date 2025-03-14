import functools
import json
import math
import os
import subprocess
import sys
import urllib.parse
from os.path import dirname

import bw2calc
import bw2data
import matplotlib.pyplot
import numpy
import pandas as pd
import requests
from bw2io.utils import activity_hash
from frozendict import deepfreeze, frozendict
from loguru import logger
from rich.console import Console
from rich.table import Table

from config import settings

from . import (
    FormatNumberJsonEncoder,
    bytrigram,
    get_normalization_weighting_factors,
    remove_detailed_impacts,
    sort_json,
    spproject,
    with_corrected_impacts,
    with_subimpacts,
)
from .impacts import main_method

# Configure logger
logger.remove()  # Remove default handler
logger.add(sys.stderr, format="{time} {level} {message}", level="INFO")


PROJECT_ROOT_DIR = dirname(dirname(__file__))

with open(os.path.join(PROJECT_ROOT_DIR, settings.impacts_file)) as f:
    IMPACTS_JSON = deepfreeze(json.load(f))


def check_ids(ingredients):
    # Check the id is lowercase and does not contain space
    for ingredient in ingredients:
        if (
            ingredient["id"].lower() != ingredient["id"]
            or ingredient["id"].replace(" ", "") != ingredient["id"]
        ):
            raise ValueError(
                f"This identifier is not lowercase or contains spaces: {ingredient['id']}"
            )


def search(dbname, search_terms, excluded_term=None):
    results = bw2data.Database(dbname).search(search_terms)
    if excluded_term:
        results = [res for res in results if excluded_term not in res["name"]]
    if not results:
        logger.warning(f"Not found in brightway db `{dbname}`: '{search_terms}'")
        return None
    if len(results) > 1:
        # if the search gives more than one results, find the one with exact name
        exact_results = [a for a in results if a["name"] == search_terms]
        if len(exact_results) == 1:
            return exact_results[0]
        else:
            results_string = "\n".join([str(result) for result in results])
            raise ValueError(
                f"This 'search' doesn’t return exaclty one matching result by name ({len(exact_results)}) in database {dbname}: {search_terms}.\nResults returned: {results_string}"
            )
    return results[0]


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
                percent_change = 100 * abs(new_value - old_value) / old_value

            if percent_change > 0.1:
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


def display_review_changes(changes, sort_by_key="%diff"):
    changes.sort(key=lambda c: c[sort_by_key])

    keys = ("trg", "name", "%diff", "from", "to")
    widths = {key: max([len(str(c[key])) for c in changes]) for key in keys}
    print("==".join(["=" * widths[key] for key in keys]))
    print("Please review the impact changes below")
    print("==".join(["=" * widths[key] for key in keys]))
    print("  ".join([f"{key.ljust(widths[key])}" for key in keys]))
    print("==".join(["=" * widths[key] for key in keys]))
    for c in changes:
        print("  ".join([f"{str(c[key]).ljust(widths[key])}" for key in keys]))
    print("==".join(["=" * widths[key] for key in keys]))
    print("  ".join([f"{key.ljust(widths[key])}" for key in keys]))
    print("==".join(["=" * widths[key] for key in keys]))
    print(f"Please review the {len(changes)} impact changes above")
    print("==".join(["=" * widths[key] for key in keys]))


def display_changes_table(changes, sort_by_key="%diff"):
    changes.sort(key=lambda c: c[sort_by_key])

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
    use_rich=False,
):
    """Display a nice sorted table of impact changes to review
    key is the field to display (id for food, uuid for textile)"""
    old = {p[key]: p for p in oldprocesses if key in p}

    if type(processes) is list:
        processes = {p[key]: p for p in processes if key in p}

    review = False
    changes = []
    for id_, p in processes.items():
        # Skip if the id doesn't exist in old processes
        if id_ not in old:
            continue
        impact_changes = get_changes(
            old_impacts=old[id_]["impacts"],
            new_impacts=processes[id_]["impacts"],
            process_name=p["name"],
            only_impacts=only_impacts,
        )

        if len(impact_changes) > 0:
            changes = changes + impact_changes
            review = True

    changes.sort(key=lambda c: c["%diff"])

    if review:
        if not use_rich:
            display_review_changes(changes)
        else:
            display_changes_table(changes)


def create_activity(dbname, new_activity_name, base_activity=None):
    """Creates a new activity by copying a base activity or from nothing. Returns the created activity"""
    if "constructed by Ecobalyse" not in new_activity_name:
        new_activity_name = f"{new_activity_name}, constructed by Ecobalyse"
    else:
        new_activity_name = f"{new_activity_name}"

    if base_activity:
        data = base_activity.as_dict().copy()
        del data["code"]
        # Id should be autogenerated or BW will throw an error
        # `id` must be created automatically, but `id=137934742532190208` given
        if "id" in data:
            del data["id"]
        data["name"] = new_activity_name
        data["System description"] = "Ecobalyse"
        data["database"] = "Ecobalyse"
        # see https://github.com/brightway-lca/brightway2-data/blob/main/CHANGES.md#40dev57-2024-10-03
        data["type"] = "processwithreferenceproduct"
        code = activity_hash(data)
        new_activity = base_activity.copy(code, **data)
    else:
        data = {
            "production amount": 1,
            "unit": "kilogram",
            # see https://github.com/brightway-lca/brightway2-data/blob/main/CHANGES.md#40dev57-2024-10-03
            "type": "processwithreferenceproduct",
            "comment": "added by Ecobalyse",
            "name": new_activity_name,
            "System description": "Ecobalyse",
        }
        code = activity_hash(data)
        new_activity = bw2data.Database(dbname).new_activity(code, **data)
        new_activity["code"] = code
    new_activity["Process identifier"] = code
    new_activity.save()
    logger.info(f"Created activity {new_activity}")
    return new_activity


def delete_exchange(activity, activity_to_delete, amount=False):
    """Deletes an exchange from an activity."""
    if amount:
        for exchange in activity.exchanges():
            if (
                exchange.input["name"] == activity_to_delete["name"]
                and exchange["amount"] == amount
            ):
                exchange.delete()
                logger.info(f"Deleted {exchange}")
                return

    else:
        for exchange in activity.exchanges():
            if exchange.input["name"] == activity_to_delete["name"]:
                exchange.delete()
                logger.info(f"Deleted {exchange}")
                return
    logger.error(f"Did not find exchange {activity_to_delete}. No exchange deleted")


def new_exchange(activity, new_activity, new_amount=None, activity_to_copy_from=None):
    """Create a new exchange. If an activity_to_copy_from is provided, the amount is copied from this activity. Otherwise, the amount is new_amount."""
    assert new_amount is not None or activity_to_copy_from is not None, (
        "No amount or activity to copy from provided"
    )
    if new_amount is None and activity_to_copy_from is not None:
        for exchange in list(activity.exchanges()):
            if exchange.input["name"] == activity_to_copy_from["name"]:
                new_amount = exchange["amount"]
                break
        else:
            logger.error(
                f"Exchange to duplicate from :{activity_to_copy_from} not found. No exchange added"
            )
            return

    new_exchange = activity.new_exchange(
        name=new_activity["name"],
        input=new_activity,
        amount=new_amount,
        type="technosphere",
        unit=new_activity["unit"],
        comment="added by Ecobalyse",
    )
    new_exchange.save()
    logger.info(f"Exchange {new_activity} added with amount: {new_amount}")


def compute_impacts(frozen_processes, default_db, impacts_py, impacts_json, plot):
    """Add impacts to processes dictionary

    Args:
        frozen_processes (frozendict): dictionary of processes of which we want to compute the impacts
    Returns:
    dictionary of processes with impacts. Example :

    {"sunflower-oil-organic": {
        "id": "sunflower-oil-organic",
        name": "...",
        "impacts": {
            "acd": 3.14,
            ...
            "ecs": 34.3,
        },
        "simapro_impacts": {
            "acd": 3.14,
            ...
            "ecs": 34.3,
        },
        "brightway_impacts": {
            "acd": 3.14,
            ...
            "ecs": 34.3,
        },
        "unit": ...
        },
    "tomato":{
    ...
    }
    """
    processes = dict(frozen_processes)
    logger.info("Computing impacts:")
    for index, (_, process) in enumerate(processes.items()):
        total = len(processes)
        # Don't compute impacts if its a hardcoded activity
        if process.get("impacts"):
            logger.info(f"This process has hardcoded impacts: {process['name']}")
            continue
        # search in brightway
        activity = cached_search(
            process.get("source", default_db), process.get("search", process["name"])
        )
        if not activity:
            raise Exception(
                f"This process was not found in brightway: {process['name']}. Searched: {process.get('search', '')}"
            )

        # Get the impacts from different sources
        logger.info(
            f"{index}/{total}: getting impacts from SimaPro for: {process['name']}"
        )
        results_simapro = compute_simapro_impacts(activity, main_method, impacts_py)
        if not results_simapro:
            logger.warning(f"SimaPro FAILED: {repr(results_simapro)}")
        else:
            # WARNING assume remote is in m3 or MJ (couldn't find unit from COM intf)
            if process["unit"] == "kWh" and isinstance(results_simapro, dict):
                results_simapro = {k: v * 3.6 for k, v in results_simapro.items()}
            if process["unit"] == "L" and isinstance(results_simapro, dict):
                results_simapro = {k: v / 1000 for k, v in results_simapro.items()}
            process["simapro_impacts"] = with_subimpacts(results_simapro)

        if plot or not results_simapro:
            logger.info(
                f"{index}/{total}: getting impacts from Brightway for: {process['name']}"
            )
            results_brightway = compute_brightway_impacts(
                activity, main_method, impacts_py
            )
            process["brightway_impacts"] = with_subimpacts(results_brightway)
            if not results_brightway:
                logger.warning(f"Brightway FAILED: {repr(results_brightway)}")

        # choose between brightway and simapro. For now we choose simapro
        if isinstance(results_simapro, dict) and results_simapro:
            # simapro succeeded
            process["impacts"] = process["simapro_impacts"].copy()
        else:
            # simapro failed (unexisting Ecobalyse project or some other reason)
            # brightway
            process["impacts"] = process["brightway_impacts"].copy()

        # remove unneeded attributes
        for attribute in ["search"]:
            if attribute in process:
                del process[attribute]

    # compute corrected impacts
    processes_corrected = with_corrected_impacts(impacts_json, processes, "impacts")

    return frozendict({k: frozendict(v) for k, v in processes_corrected.items()})


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


def csv_export_impact_comparison(compared_impacts, folder):
    rows = []
    for product_id, process in compared_impacts.items():
        simapro_impacts = process.get("simapro_impacts", {})
        brightway_impacts = process.get("brightway_impacts", {})
        for impact in simapro_impacts:
            row = {
                "id": product_id,
                "name": process["name"],
                "impact": impact,
                "simapro": simapro_impacts.get(impact, 0),
                "brightway": brightway_impacts.get(impact, 0),
            }
            row["diff_abs"] = abs(row["simapro"] - row["brightway"])
            row["diff_rel"] = (
                row["diff_abs"] / abs(row["simapro"]) if row["simapro"] != 0 else None
            )

            rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv(
        os.path.join(PROJECT_ROOT_DIR, folder, settings.compared_impacts_file),
        index=False,
    )


def export_json(json_data, filename, sort=False):
    if sort:
        json_data = sort_json(json_data)

    logger.info(f"Exporting {filename}...")
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
        display_changes("id", oldprocesses, processes_corrected_impacts, use_rich=True)


def export_processes_to_dirs(
    processes_aggregated_path,
    processes_impacts_path,
    processes_corrected_impacts,
    processes_aggregated_impacts,
    dirs,
    extra_data=None,
    extra_path=None,
):
    exported_files = []

    for dir in dirs:
        logger.info("")
        logger.info(f"-> Exporting to {dir}...")
        processes_impacts = os.path.join(dir, processes_impacts_path)
        processes_aggregated = os.path.join(dir, processes_aggregated_path)

        if extra_data is not None and extra_path is not None:
            extra_file = os.path.join(dir, extra_path)
            export_json(extra_data, extra_file, sort=True)
            exported_files.append(extra_file)

        # Export results
        export_json(
            list(processes_aggregated_impacts.values()), processes_impacts, sort=True
        )

        exported_files.append(processes_impacts)
        export_json(
            remove_detailed_impacts(list(processes_aggregated_impacts.values())),
            processes_aggregated,
            sort=True,
        )
        exported_files.append(processes_aggregated)

    return exported_files


def load_json(filename):
    """
    Load JSON data from a file.
    """
    with open(filename, "r") as file:
        return json.load(file)


@functools.cache
def cached_search(dbname, search_terms, excluded_term=None):
    return search(dbname, search_terms, excluded_term)


def find_id(dbname, activity):
    if (search_terms := activity.get("search")) is not None:
        search_result = cached_search(dbname, search_terms)
        if search_result is not None:
            return search_result.get("Process identifier", activity["id"])

    return None


def compute_simapro_impacts(activity, method, impacts_py):
    project, library = spproject(activity)
    name = (
        activity["name"]
        if project != "WFLDB"
        # TODO this should probably done through disabling a strategy
        else f"{activity['name']}/{activity['location']} U"
    )
    strprocess = urllib.parse.quote(name, encoding=None, errors=None)
    project = urllib.parse.quote(project, encoding=None, errors=None)
    library = urllib.parse.quote(library, encoding=None, errors=None)
    method = urllib.parse.quote(main_method, encoding=None, errors=None)
    api_request = f"http://simapro.ecobalyse.fr:8000/impact?process={strprocess}&project={project}&library={library}&method={method}"
    logger.debug(f"SimaPro API request: {api_request}")

    try:
        response = requests.get(api_request)
    except requests.exceptions.ConnectTimeout:
        logger.warning("SimaPro did not answer! Is it started?")
        return dict()

    try:
        json_content = json.loads(response.content)

        # If Simapro doesn't return a dict, it's most likely an error
        # (project not found) Don't do anything and return None,
        # BW will be used as a replacement
        if isinstance(json_content, dict):
            return bytrigram(impacts_py, json_content)
    except ValueError:
        pass

    return dict()


def compute_brightway_impacts(activity, method, impacts_py):
    results = dict()
    lca = bw2calc.LCA({activity: 1})
    lca.lci()
    for key, method in impacts_py.items():
        lca.switch_method(method)
        lca.lcia()
        results[key] = float("{:.10g}".format(lca.score))
        logger.debug(f"{activity}  {key}: {lca.score}")

    return results


def generate_compare_graphs(processes, impacts_py, graph_folder, output_dirname, plot):
    csv_export_impact_comparison(processes, output_dirname)
    output = dict()
    for process_name, values in processes.items():
        name = values["name"]
        if "simapro_impacts" not in values and "brightway_impacts" not in values:
            logger.info(f"This hardcopied process cannot be plot: {name}")
        elif plot:
            logger.info(f"Plotting {name}")
            os.makedirs(graph_folder, exist_ok=True)
            plot_impacts(
                process_name=name,
                impacts_smp=values.get("simapro_impacts", {}),
                impacts_bw=values.get("brightway_impacts", {}),
                folder=graph_folder,
                impacts_py=IMPACTS_JSON,
            )
        result = dict(values)
        if "simapro_impacts" in result:
            del result["simapro_impacts"]
        if "brightway_impacts" in result:
            del result["brightway_impacts"]
        output[process_name] = result
    if plot:
        logger.info("Charts have been generated and saved as PNG files.")
    return frozendict(output)
