#!/usr/bin/env python

"""Materials and processes export for textile"""

import os
import sys
from os.path import abspath, dirname

import bw2data
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
    compute_impacts,
    export_processes_to_dirs,
    find_id,
    format_json,
    generate_compare_graphs,
    load_json,
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
        # those are removed at the end:
        **({"search": activity["search"]} if "search" in activity else {}),
    }


if __name__ == "__main__":
    bw2data.projects.set_current(settings.bw.project)

    activities = tuple(
        load_json(os.path.join(PROJECT_TEXTILE_DIR, settings.activities_file))
    )

    materials = create_material_list(activities)

    check_ids(materials)
    processes = create_process_list(activities)

    # processes with impacts, impacts_simapro and impacts_brightway
    processes_impacts = compute_impacts(
        processes, settings.bw.ecoinvent, impacts_py, IMPACTS_JSON
    )
    # processes with impacts only
    processes_impacts = generate_compare_graphs(
        processes_impacts, impacts_py, GRAPH_FOLDER, settings.textile.dirname
    )

    processes_aggregated_impacts = with_aggregated_impacts(
        IMPACTS_JSON, processes_impacts
    )

    exported_files = export_processes_to_dirs(
        os.path.join(settings.textile.dirname, settings.processes_aggregated_file),
        os.path.join(settings.textile.dirname, settings.processes_impacts_file),
        processes_impacts,
        processes_aggregated_impacts,
        dirs_to_export_to,
        extra_data=materials,
        extra_path=os.path.join(
            settings.textile.dirname, settings.textile.materials_file
        ),
    )

    format_json(" ".join(exported_files))
