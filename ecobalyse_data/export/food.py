import json
from typing import List, Optional, Tuple

import bw2calc
import matplotlib.pyplot as plt
import pandas as pd

import config
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


def compute_ecs_for_activities(
    activities: List[dict], ecosystemic_factors, feed_file_content, ugb
) -> dict[str, dict]:
    ecs_for_activities = {}
    activities_by_id = {activity["id"]: activity for activity in activities}

    for activity in activities:
        id = activity["id"]

        if id in ecs_for_activities:
            # The ecs for this activity was already computed (a dependency of an animal activity)
            # skip it
            continue

        # This is a vegetable
        if all(
            activity.get(key) for key in ["landOccupation", "cropGroup", "scenario"]
        ):
            services = compute_vegetal_ecosystemic_services(
                activity, ecosystemic_factors
            )

            ecs_for_activities[id] = services

        # This is an animal
        if id in feed_file_content:
            ecs_for_activities = compute_animal_ecosystemic_services(
                activity,
                ecs_for_activities,
                activities_by_id,
                ecosystemic_factors,
                feed_file_content,
                ugb,
            )

    return ecs_for_activities


def compute_livestock_density_ecosystemic_service(
    animal_activity_properties, ugb, ecosystemic_factors
):
    try:
        livestock_density_per_ugb = ecosystemic_factors[
            animal_activity_properties["animalGroup1"]
        ]["livestockDensity"][animal_activity_properties["scenario"]]
        ugb_per_kg = ugb[animal_activity_properties["animalGroup2"]][
            animal_activity_properties["animalProduct"]
        ]
        return livestock_density_per_ugb * ugb_per_kg
    except KeyError as e:
        print(
            f"Error processing animal with ID {animal_activity_properties.get('id', 'Unknown')}: Missing key {e}"
        )
        raise


def compute_vegetal_ecosystemic_services(
    activity, ecosystemic_factors
) -> Optional[dict]:
    services = {}

    for eco_service in config.ecosystemic_services_list:
        factor_raw = ecosystemic_factors[activity["cropGroup"]][eco_service][
            activity["scenario"]
        ]
        factor_transformed = ecs_transform(eco_service, factor_raw)
        factor_final = factor_transformed * activity["landOccupation"]
        services[eco_service] = float("{:.5g}".format(factor_final))

    return services


def compute_animal_ecosystemic_services(
    activity,
    ecs_for_activities,
    activities_by_id,
    ecosystemic_factors,
    feed_file_content,
    ugb,
) -> dict:
    services = {}

    id = activity["id"]
    feed_quantities = feed_file_content[id]

    hedges = 0
    plotSize = 0
    cropDiversity = 0

    # Go throug each dependency of the animal
    for feed_activity_id, quantity in feed_quantities.items():
        # We don't have the ecs for the corresponding vegetable, so we need to compute it
        if feed_activity_id not in ecs_for_activities:
            feed_activity_services = compute_vegetal_ecosystemic_services(
                activities_by_id[feed_activity_id], ecosystemic_factors
            )
            ecs_for_activities[feed_activity_id] = feed_activity_services

        feed_services = ecs_for_activities[feed_activity_id]
        hedges += quantity * feed_services["hedges"]
        plotSize += quantity * feed_services["plotSize"]
        cropDiversity += quantity * feed_services["cropDiversity"]

    services["hedges"] = hedges
    services["plotSize"] = plotSize
    services["cropDiversity"] = cropDiversity

    services["permanentPasture"] = feed_quantities.get(
        # "grazed-grass-permanent", 0
        "c88d387e-8435-4741-b742-0094dbdcee45",
        0,
    )

    services["livestockDensity"] = compute_livestock_density_ecosystemic_service(
        activity, ugb, ecosystemic_factors
    )

    ecs_for_activities[id] = services

    return ecs_for_activities


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

    ecosystemic_factors = load_ecosystemic_dic(ecosystemic_factors_path)

    feed_file_content = {}

    with open(feed_file_path, "r") as file:
        feed_file_content = json.load(file)

    ugb = load_ugb_dic(ugb_file_path)

    materials = activities_to_ingredients(
        activities, ecosystemic_factors, feed_file_content, ugb
    )

    materials_dict = [material.model_dump(exclude_none=True) for material in materials]

    exported_files = []
    for materials_path in ingredients_paths:
        export_json(materials_dict, materials_path, sort=True)

        exported_files.append(materials_path)

    format_json(" ".join(exported_files))

    for materials_path in exported_files:
        logger.info(f"-> Exported {len(materials_dict)} materials to {materials_path}")


def activities_to_ingredients(
    activities: List[dict], ecosystemic_factors, feed_file_content, ugb
) -> List[Ingredient]:
    ecs_by_id = compute_ecs_for_activities(
        activities, ecosystemic_factors, feed_file_content, ugb
    )
    return [
        activity_to_ingredient(activity, ecs_by_id)
        for activity in list(activities)
        if "ingredient" in activity.get("categories", [])
    ]


def activity_to_ingredient(eco_activity: dict, ecs_by_id: dict) -> Ingredient:
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
        default=bw_activity.get("Process identifier", eco_activity["id"]),
        defaultOrigin=eco_activity["defaultOrigin"],
        density=eco_activity["ingredientDensity"],
        ecosystemicServices=ecs_by_id.get(eco_activity["id"]),
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


def plot_ecs_transformations(save_path=None):
    # Create a range of values for x-axis (input values for ecs_transform)
    plot_characteristic_dic = {
        "hedges": {"range": range(0, 200), "unit": "Mètre linéaire de haie/ha"},
        "plotSize": {"range": range(0, 25), "unit": "Taille de parcelle (ha)"},
        "cropDiversity": {"range": range(0, 30), "unit": "Simpson number"},
    }  # Adjust the range based on expected values

    num_plots = len(config.ecosystemic_services_list)

    # Create subplots
    fig, axes = plt.subplots(num_plots, 1, figsize=(10, 6 * num_plots))

    # Check if axes is a single axis object or an array of axes
    if num_plots == 1:
        axes = [axes]

    # Add the title text at the top of the plot
    fig.suptitle(
        "The greater the transformed value, the higher the ecosystemic service value, the lower the overall environmental impact",
        fontsize=14,
    )
    # Plotting the transformations for each ecosystemic service in a separate subplot
    for index, eco_service in enumerate(config.ecosystemic_services_list):
        value_range = plot_characteristic_dic[eco_service]["range"]
        transformed_values = [
            ecs_transform(eco_service, value) for value in value_range
        ]
        ax = axes[index]
        ax.plot(value_range, transformed_values, label=eco_service)
        ax.set_title(f"{eco_service}")
        ax.set_xlabel(plot_characteristic_dic[eco_service]["unit"])
        ax.set_ylabel("Transformed Value")
        ax.legend()
        ax.grid(True)

    if save_path:
        plt.savefig(save_path, bbox_inches="tight")

    plt.tight_layout()
