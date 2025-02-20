#!/usr/bin/env python

"""Ingredients and processes export for food"""

import argparse
import os
from os.path import abspath, dirname

import bw2calc
import bw2data
from frozendict import frozendict

from common import brightway_patch as brightway_patch
from common import (
    fix_unit,
    with_aggregated_impacts,
)
from common.export import (
    IMPACTS_JSON,
    cached_search,
    check_ids,
    compute_impacts,
    export_json,
    export_processes_to_dirs,
    find_id,
    format_json,
    generate_compare_graphs,
    load_json,
)
from common.impacts import impacts as impacts_py
from config import settings
from food.ecosystemic_services.ecosystemic_services import (
    compute_animal_ecosystemic_services,
    compute_vegetal_ecosystemic_services,
    load_ecosystemic_dic,
    load_ugb_dic,
)

PROJECT_ROOT_DIR = dirname(dirname(abspath(__file__)))

dirs_to_export_to = [settings.output_dir]

if settings.local_export:
    dirs_to_export_to.append(os.path.join(PROJECT_ROOT_DIR, "public", "data"))

# Configuration

PROJECT_FOOD_DIR = os.path.join(PROJECT_ROOT_DIR, settings.food.dirname)
ACTIVITIES_FILE = os.path.join(PROJECT_FOOD_DIR, settings.activities_file)

LAND_OCCUPATION_METHOD = ("selected LCI results", "resource", "land occupation")
GRAPH_FOLDER = f"{PROJECT_ROOT_DIR}/food/impact_comparison"


def create_ingredient_list(activities_tuple):
    print("Creating ingredient list...")
    return tuple(
        [
            to_ingredient(activity)
            for activity in list(activities_tuple)
            if "ingredient" in activity.get("process_categories", [])
        ]
    )


def to_ingredient(activity):
    return {
        "alias": activity["alias"],
        "categories": activity.get("ingredient_categories", []),
        "default": find_id(activity.get("database", settings.bw.agribalyse), activity),
        "default_origin": activity["default_origin"],
        "density": activity["density"],
        **({"crop_group": activity["crop_group"]} if "crop_group" in activity else {}),
        "ecosystemicServices": activity.get("ecosystemicServices", {}),
        "id": activity["id"],
        "inedible_part": activity["inedible_part"],
        **(
            {"land_occupation": activity["land_occupation"]}
            if "land_occupation" in activity
            else {}
        ),
        "name": activity["name"],
        "raw_to_cooked_ratio": activity["raw_to_cooked_ratio"],
        **({"scenario": activity["scenario"]} if "scenario" in activity else {}),
        "search": activity["search"],
        "transport_cooling": activity["transport_cooling"],
        "visible": activity["visible"],
    }


def compute_land_occupation(activities_tuple):
    """"""
    print("Computing land occupation for activities")
    activities = list(activities_tuple)
    updated_activities = []
    total = len(activities)
    for index, activity in enumerate(activities):
        print(f"{index}/{total} Computing land occupation of {activity['name']}")
        if "land_occupation" not in activity and "ingredient" in activity.get(
            "process_categories", []
        ):
            lca = bw2calc.LCA(
                {
                    cached_search(
                        activity.get("database", settings.bw.agribalyse),
                        activity["search"],
                    ): 1
                }
            )
            lca.lci()
            lca.switch_method(LAND_OCCUPATION_METHOD)
            lca.lcia()
            activity["land_occupation"] = float("{:.10g}".format(lca.score))
        updated_activities.append(frozendict(activity))
    return tuple(updated_activities)


def create_process_list(activities):
    print("Creating process list...")

    return frozendict({activity["id"]: to_process(activity) for activity in activities})


def to_process(activity):
    return {
        "categories": activity.get("process_categories"),
        "comment": (
            prod[0].get("comment", "")
            if (
                prod := list(
                    cached_search(
                        activity.get("database", settings.bw.agribalyse),
                        activity["search"],
                    ).production()
                )
            )
            else activity.get("comment", "")
        ),
        "density": 0,
        "displayName": activity["name"],
        "elec_MJ": 0,
        "heat_MJ": 0,
        "id": activity["id"],
        "sourceId": find_id(activity.get("database", settings.bw.agribalyse), activity),
        "impacts": {},
        "name": cached_search(
            activity.get("database", settings.bw.agribalyse), activity["search"]
        )["name"],
        "source": activity.get("database", settings.bw.agribalyse),
        "unit": fix_unit(
            cached_search(
                activity.get("database", settings.bw.agribalyse), activity["search"]
            )["unit"]
        ),
        # those are removed at the end:
        "search": activity["search"],
        "waste": 0,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--plot",
        action="store_true",
        help="Also plot comparison graphs between Brightway and SimaPro",
    )
    args = parser.parse_args()
    bw2data.projects.set_current(settings.bw.project)
    bw2data.config.p["biosphere_database"] = "biosphere3"

    activities = tuple(load_json(ACTIVITIES_FILE))

    activities_land_occ = compute_land_occupation(activities)
    ingredients = create_ingredient_list(activities_land_occ)
    check_ids(ingredients)

    processes = create_process_list(activities_land_occ)

    # ecosystemic factors
    ecosystemic_factors = load_ecosystemic_dic(
        os.path.join(
            PROJECT_FOOD_DIR,
            settings.food.ecosystemic_factors_file,
        )
    )
    ingredients_veg_es = compute_vegetal_ecosystemic_services(
        ingredients, ecosystemic_factors
    )

    feed_file = load_json(os.path.join(PROJECT_FOOD_DIR, settings.food.feed_file))
    ugb = load_ugb_dic(os.path.join(PROJECT_FOOD_DIR, settings.food.ugb_file))
    ingredients_animal_es = compute_animal_ecosystemic_services(
        ingredients_veg_es, activities_land_occ, ecosystemic_factors, feed_file, ugb
    )

    # processes with impacts, impacts_simapro and impacts_brightway
    processes_impacts = compute_impacts(
        processes, settings.bw.agribalyse, impacts_py, IMPACTS_JSON
    )
    # processes with impacts only
    processes_impacts = generate_compare_graphs(
        processes_impacts,
        impacts_py,
        GRAPH_FOLDER,
        settings.food.dirname,
        plot=args.plot,
    )

    processes_aggregated_impacts = with_aggregated_impacts(
        IMPACTS_JSON, processes_impacts
    )

    export_json(activities_land_occ, ACTIVITIES_FILE, sort=True)

    exported_files = export_processes_to_dirs(
        os.path.join(settings.food.dirname, settings.processes_aggregated_file),
        os.path.join(settings.food.dirname, settings.processes_impacts_file),
        processes_impacts,
        processes_aggregated_impacts,
        dirs_to_export_to,
        extra_data=ingredients_animal_es,
        extra_path=os.path.join(settings.food.dirname, settings.food.ingredients_file),
    )
    exported_files.append(ACTIVITIES_FILE)

    format_json(" ".join(exported_files))
