#!/usr/bin/env python

"""Materials and processes export for textile"""

import os
import sys
from os.path import abspath, dirname

import bw2data
import pandas as pd
from frozendict import frozendict

from common import brightway_patch as brightway_patch
from common import (
    fix_unit,
    with_aggregated_impacts,
    with_corrected_impacts,
)
from common.export import (
    IMPACTS_JSON,
    cached_search,
    check_ids,
    compare_impacts,
    compute_impacts,
    export_processes_to_dirs,
    find_id,
    load_json,
    order_json,
    plot_impacts,
)
from common.impacts import impacts as impacts_py
from config import settings

BW_DATABASES = bw2data.databases

PROJECT_ROOT_DIR = dirname(dirname(abspath(__file__)))
PROJECT_TEXTILE_DIR = os.path.join(PROJECT_ROOT_DIR, settings.textile.dirname)

dirs_to_export_to = [settings.output_dir]

if settings.local_export:
    dirs_to_export_to.append(os.path.join(PROJECT_ROOT_DIR, "public", "data"))


# Configuration
GRAPH_FOLDER = f"{PROJECT_ROOT_DIR}/textile/impact_comparison"


def create_material_list(activities_tuple):
    print("Creating material list...")
    return tuple(
        [
            to_material(activity)
            for activity in list(activities_tuple)
            if activity["category"] == "material"
        ]
    )


def to_material(activity):
    return {
        "id": activity["material_id"],
        "materialProcessUuid": activity["id"],
        "recycledProcessUuid": activity.get("recycledProcessUuid"),
        "recycledFrom": activity.get("recycledFrom"),
        "name": activity["shortName"],
        "shortName": activity["shortName"],
        "origin": activity["origin"],
        "primary": activity.get("primary"),
        "geographicOrigin": activity["geographicOrigin"],
        "defaultCountry": activity["defaultCountry"],
        "priority": activity.get("priority"),
        "cff": activity.get("cff"),
    }


def create_process_list(activities):
    print("Creating process list...")
    return frozendict({activity["id"]: to_process(activity) for activity in activities})


def to_process(activity):
    return {
        "id": activity["id"],
        "name": cached_search(
            activity.get("source", settings.bw.ecoinvent), activity["search"]
        )["name"]
        if "search" in activity and activity["source"] in BW_DATABASES
        else activity.get("name", activity["displayName"]),
        "displayName": activity["displayName"],
        "unit": fix_unit(
            cached_search(
                activity.get("source", settings.bw.ecoinvent), activity["search"]
            )["unit"]
            if "search" in activity and activity["source"] in BW_DATABASES
            else activity["unit"]
        ),
        "source": activity["source"],
        "sourceId": find_id(activity.get("database", settings.bw.ecoinvent), activity),
        "comment": activity["comment"],
        "categories": activity["categories"],
        **(
            {"impacts": activity["impacts"].copy()}
            if "impacts" in activity
            else {"impacts": {}}
        ),
        "density": activity["density"],
        "heat_MJ": activity["heat_MJ"],
        "elec_MJ": activity["elec_MJ"],
        "waste": activity["waste"],
        "alias": activity["alias"],
        # those are removed at the end:
        **({"search": activity["search"]} if "search" in activity else {}),
    }


def csv_export_impact_comparison(compared_impacts):
    rows = []
    for product_id, process in compared_impacts.items():
        simapro_impacts = process.get("simapro_impacts", {})
        brightway_impacts = process.get("brightway_impacts", {})
        for impact in simapro_impacts:
            row = {
                "id": product_id,
                "name": process["name"],
                "impact": impact,
                "simapro": simapro_impacts.get(impact),
                "brightway": brightway_impacts.get(impact),
            }
            row["diff_abs"] = abs(row["simapro"] - row["brightway"])
            row["diff_rel"] = (
                row["diff_abs"] / abs(row["simapro"]) if row["simapro"] != 0 else None
            )

            rows.append(row)

    df = pd.DataFrame(rows)
    df.to_csv(
        os.path.join(PROJECT_TEXTILE_DIR, settings.compared_impacts_file),
        index=False,
    )


if __name__ == "__main__":
    # bw2data.config.p["biosphere_database"] = "biosphere3"

    activities = tuple(
        load_json(os.path.join(PROJECT_TEXTILE_DIR, settings.activities_file))
    )

    materials = create_material_list(activities)

    check_ids(materials)
    processes = create_process_list(activities)

    if len(sys.argv) == 1:  # just export.py
        processes_impacts = compute_impacts(
            processes, settings.bw.ecoinvent, impacts_py
        )
    elif len(sys.argv) > 1 and sys.argv[1] == "compare":  # export.py compare
        impacts_compared_dic = compare_impacts(
            processes, settings.bw.ecoinvent, impacts_py, IMPACTS_JSON
        )
        csv_export_impact_comparison(impacts_compared_dic)
        for process_name, values in impacts_compared_dic.items():
            displayName = processes[process_name]["displayName"]
            print(f"Plotting {displayName}")
            if "simapro_impacts" not in values and "brightway_impacts" not in values:
                print(f"This hardcopied process cannot be plot: {displayName}")
                continue
            simapro_impacts = values["simapro_impacts"]
            brightway_impacts = values["brightway_impacts"]
            os.makedirs(GRAPH_FOLDER, exist_ok=True)
            plot_impacts(
                displayName,
                simapro_impacts,
                brightway_impacts,
                GRAPH_FOLDER,
                IMPACTS_JSON,
            )
            print("Charts have been generated and saved as PNG files.")
        sys.exit(0)
    else:
        print("Wrong argument: either no args or 'compare'")
        sys.exit(1)

    processes_corrected_impacts = with_corrected_impacts(
        IMPACTS_JSON, processes_impacts
    )
    processes_aggregated_impacts = with_aggregated_impacts(
        IMPACTS_JSON, processes_corrected_impacts
    )

    export_processes_to_dirs(
        os.path.join(settings.textile.dirname, settings.processes_aggregated_file),
        os.path.join(settings.textile.dirname, settings.processes_impacts_file),
        processes_corrected_impacts,
        processes_aggregated_impacts,
        dirs_to_export_to,
        extra_data=order_json(materials),
        extra_path=os.path.join(
            settings.textile.dirname, settings.textile.materials_file
        ),
    )
