import json
from typing import List, Optional, Tuple

import bw2calc
import pandas as pd

from common.export import (
    export_json,
    format_json,
)
from ecobalyse_data.bw.search import cached_search_one
from ecobalyse_data.logging import logger
from models.process import Ingredient

THRESHOLD_HEDGES = 140  # ml/ha
THRESHOLD_PLOTSIZE = 8  # ha
THRESHOLD_CROPDIVERSITY = 7.5  # simpson number

ecosystemic_services_list = ["hedges", "plotSize", "cropDiversity"]


# For each eco_service, we associate a transformation function
# to get a visual idea of the function, look at ecs_transformations.png
TRANSFORM = {
    "hedges": (THRESHOLD_HEDGES, lambda x: x / THRESHOLD_HEDGES, lambda x: 1),
    "plotSize": (THRESHOLD_PLOTSIZE, lambda x: 1 - x / THRESHOLD_PLOTSIZE, lambda x: 0),
    "cropDiversity": (
        THRESHOLD_CROPDIVERSITY,
        lambda x: 0,
        lambda x: x - THRESHOLD_CROPDIVERSITY,
    ),
}


def ecs_transform(eco_service, value):
    if value < 0:
        raise ValueError(f"complement {eco_service} input value can't be lower than 0")

    if eco_service not in TRANSFORM:
        raise ValueError(f"Unknown complement: {eco_service}")

    threshold, func_below, func_above = TRANSFORM[eco_service]
    if value < threshold:
        return func_below(value)
    else:
        return func_above(value)


def load_ecosystemic_dic(PATH):
    """Load ecosystemic csv as dictionary"""
    ecosystemic_factors_csv = pd.read_csv(PATH, sep=";")
    ecosystemic_factors = {}
    for _, row in ecosystemic_factors_csv.iterrows():
        cropGroup = row["group"]
        ecosystemic_factors[cropGroup] = {
            "hedges": {
                "reference": row["hedges_reference"],
                "organic": row["hedges_organic"],
                "import": row["hedges_import"],
            },
            "plotSize": {
                "reference": row["plotSize_reference"],
                "organic": row["plotSize_organic"],
                "import": row["plotSize_import"],
            },
            "cropDiversity": {
                "reference": row["cropDiversity_reference"],
                "organic": row["cropDiversity_organic"],
                "import": row["cropDiversity_import"],
            },
            "livestockDensity": {
                "reference": row["livestockDensity_reference"],
                "organic": row["livestockDensity_organic"],
                "import": row["livestockDensity_import"],
            },
        }
    return ecosystemic_factors


def load_ugb_dic(PATH):
    ugb_df = pd.read_csv(PATH, sep=";")
    ugb_dic = {}
    for _, row in ugb_df.iterrows():
        group = row["animalGroup2"]
        if group not in ugb_dic:
            ugb_dic[group] = {}
        ugb_dic[group][row["animalProduct"]] = row["value"]

    return ugb_dic


def compute_land_occupation(
    bw_activity,
    land_occupation_method: Tuple[str, str, str] = (
        "selected LCI results",
        "resource",
        "land occupation",
    ),
):
    logger.info(f"-> Computing land occupation for {bw_activity}")
    lca = bw2calc.LCA({bw_activity: 1})
    lca.lci()
    lca.switch_method(land_occupation_method)
    lca.lcia()
    logger.info(f"-> Finished computing land occupation for {bw_activity} {lca.score}")

    return float(lca.score)


def compute_vegetal_ecosystemic_services(
    activity, ecosystemic_factors
) -> Optional[dict]:
    if all(activity.get(key) for key in ["landOccupation", "cropGroup", "scenario"]):
        services = {}
        for eco_service in ecosystemic_services_list:
            factor_raw = ecosystemic_factors[activity["cropGroup"]][eco_service][
                activity["scenario"]
            ]
            factor_transformed = ecs_transform(eco_service, factor_raw)
            factor_final = factor_transformed * activity["landOccupation"]
            services[eco_service] = float("{:.5g}".format(factor_final))

        return services


# def compute_animal_ecosystemic_services(
#     activity, ecosystemic_factors, feed_file_content, ugb
# ):
#
#     hedges = 0
#     plotSize = 0
#     cropDiversity = 0
#
#     ecosystemicServices = {}
#
#     if activity["id"] in feed_file_content:
#         feed_quantities = feed_file_content[activity["id"]]
#
#     for feed_name, quantity in feed_quantities.items():
#         assert feed_name in ingredients_dic, (
#             f"feed {feed_name} is not present in ingredients"
#         )
#         feed_properties = ingredients_dic[feed_name]
#         hedges += quantity * feed_properties["ecosystemicServices"]["hedges"]
#         plotSize += quantity * feed_properties["ecosystemicServices"]["plotSize"]
#         cropDiversity += (
#             quantity * feed_properties["ecosystemicServices"]["cropDiversity"]
#         )
#     ecosystemicServices["hedges"] = hedges
#     ecosystemicServices["plotSize"] = plotSize
#     ecosystemicServices["cropDiversity"] = cropDiversity
#
#     ecosystemicServices["permanentPasture"] = feed_quantities.get(
#         # "grazed-grass-permanent", 0
#         "c88d387e-8435-4741-b742-0094dbdcee45",
#         0,
#     )
#
#     # ecosystemicServices["livestockDensity"] = (
#     #     compute_livestockDensity_ecosystemic_service(
#     #         frozendict(activities_dic[animalProduct]), ugb, ecosystemic_factors
#     #     )
#     # )
#     ingredients_dic_updated[animalProduct]["ecosystemicServices"] = (
#         ecosystemicServices
#     )


def activities_to_ingredients_json(
    activities_path: str,
    ingredients_paths: List[str],
    ecosystemic_factors_path: str,
    feed_file_path: str,
    ugb_file_path: str,
) -> List[Ingredient]:
    logger.info(f"-> Loading activities file {activities_path}")

    activities = []
    with open(activities_path, "r") as file:
        activities = json.load(file)

    _ecosystemic_factors = load_ecosystemic_dic(ecosystemic_factors_path)

    _feed_file_content = {}

    with open(feed_file_path, "r") as file:
        _feed_file_content = json.load(file)

    _ugb = load_ugb_dic(ugb_file_path)

    materials = activities_to_ingredients(activities)

    materials_dict = [material.model_dump(exclude_none=True) for material in materials]

    exported_files = []
    for materials_path in ingredients_paths:
        export_json(materials_dict, materials_path, sort=True)

        exported_files.append(materials_path)

    format_json(" ".join(exported_files))

    for materials_path in exported_files:
        logger.info(f"-> Exported {len(materials_dict)} materials to {materials_path}")


def activities_to_ingredients(activities: List[dict]) -> List[Ingredient]:
    return [
        activity_to_ingredient(activity)
        for activity in list(activities)
        if "ingredient" in activity.get("categories", [])
    ]


def activity_to_ingredient(eco_activity: dict) -> Ingredient:
    bw_activity = cached_search_one(
        eco_activity.get("source"), eco_activity.get("search")
    )
    land_occupation = eco_activity.get("landOccupation")

    if not land_occupation:
        land_occupation = compute_land_occupation(bw_activity)

    return Ingredient(
        alias=eco_activity["alias"],
        categories=eco_activity.get("ingredientCategories", []),
        cropGroup=eco_activity.get("cropGroup"),
        default=bw_activity.get("Process identifier", eco_activity.get("id")),
        defaultOrigin=eco_activity["defaultOrigin"],
        density=eco_activity["ingredientDensity"],
        ecosystemicServices=None,
        id=eco_activity["id"],
        inediblePart=eco_activity["inediblePart"],
        landOccupation=land_occupation,
        name=eco_activity["displayName"],
        rawToCookedRatio=eco_activity["rawToCookedRatio"],
        scenario=eco_activity.get("scenario"),
        search=eco_activity["search"],
        transportCooling=eco_activity["transportCooling"],
        visible=eco_activity["visible"],
    )
