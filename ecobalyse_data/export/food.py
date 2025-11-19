import csv
import json
from enum import StrEnum
from multiprocessing import Pool
from typing import List, Optional, Tuple

import bw2calc
import matplotlib.pyplot as plt

import config
from common.export import (
    export_json,
    get_process_id,
)
from ecobalyse_data.bw.search import cached_search_one
from ecobalyse_data.logging import logger
from models.process import EcosystemicServices, Ingredient


class Scenario(StrEnum):
    ORGANIC = "organic"
    REFERENCE = "reference"
    IMPORT = "import"


class DefaultOrigin(StrEnum):
    FRANCE = "France"
    EUROPE_AND_MAGHREB = "EuropeAndMaghreb"
    OUT_OF_EUROPE_AND_MAGHREB = "OutOfEuropeAndMaghreb"
    OUT_OF_EUROPE_AND_MAGHREB_BY_PLANE = "OutOfEuropeAndMaghrebByPlane"


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


def float_or_none(value) -> Optional[float]:
    try:
        return float(value)
    except ValueError:
        return None


def gen_factors(row):
    es = {}
    for kind in ["hedges", "plotSize", "cropDiversity", "livestockDensity"]:
        es[kind] = {}
        for key in ["reference", "organic", "import"]:
            es[kind][key] = float_or_none(row[f"{kind}_{key}"])
    return es


def load_ecosystemic_dic(PATH):
    """Load ecosystemic csv as dictionary"""

    ecosystemic_factors = {}

    with open(PATH, "r", encoding="utf-8-sig") as csvfile:
        reader = csv.DictReader(csvfile, delimiter=";")
        for row in reader:
            cropGroup = row.get("group")
            ecosystemic_factors[cropGroup] = gen_factors(row)
    return ecosystemic_factors


def load_ugb_dic(PATH):
    ugb_dic = {}

    with open(PATH, "r", encoding="utf-8-sig") as csvfile:
        reader = csv.DictReader(csvfile, delimiter=";")
        for row in reader:
            group = row["animalGroup2"]
            if group not in ugb_dic:
                ugb_dic[group] = {}
            ugb_dic[group][row["animalProduct"]] = float(row["value"])

    return ugb_dic


def compute_land_occupation(
    bw_activity,
    land_occupation_method: Tuple[str, str, str] = (
        "selected LCI results",
        "resource",
        "land occupation",
    ),
):
    logger.debug(f"-> Computing land occupation for {bw_activity}")
    lca = bw2calc.LCA({bw_activity: 1})
    lca.lci()
    lca.switch_method(land_occupation_method)
    lca.lcia()
    logger.debug(f"-> Finished computing land occupation for {bw_activity} {lca.score}")

    return float(lca.score)


def compute_ecs_for_activities(
    activities: List[dict], ecosystemic_factors, feed_file_content, ugb
) -> dict[str, dict]:
    ecs_for_activities = {}

    metadata_by_alias = {}
    for activity in activities:
        for food_metadata in activity["metadata"]["food"]:
            metadata_by_alias[food_metadata["alias"]] = food_metadata

    for activity in activities:
        for food_metadata in activity["metadata"]["food"]:
            alias = food_metadata["alias"]
            if alias in ecs_for_activities:
                # The ecs for this activity was already computed (a dependency of an animal activity)
                # skip it
                continue
            # This is a vegetable
            if all(
                food_metadata.get(key)
                for key in ["landOccupation", "cropGroup", "scenario"]
            ):
                services = compute_vegetal_ecosystemic_services(
                    food_metadata, ecosystemic_factors
                )

                ecs_for_activities[alias] = services

            # This is an animal
            elif alias in feed_file_content:
                ecs_for_activities = compute_animal_ecosystemic_services(
                    food_metadata,
                    ecs_for_activities,
                    metadata_by_alias,
                    ecosystemic_factors,
                    feed_file_content,
                    ugb,
                )
            else:
                displayName = activity["displayName"]
                logger.warning(
                    f"{displayName} doesn’t have any food complements associated"
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
        logger.error(
            f"Error processing animal with ID {animal_activity_properties.get('id', 'Unknown')}: Missing key {e}"
        )
        raise


def compute_vegetal_ecosystemic_services(food_metadata, ecosystemic_factors) -> dict:
    services = {}
    for eco_service in config.ecosystemic_services_list:
        factor_raw = ecosystemic_factors[food_metadata["cropGroup"]][eco_service][
            food_metadata["scenario"]
        ]
        factor_transformed = ecs_transform(eco_service, factor_raw)
        factor_final = factor_transformed * food_metadata["landOccupation"]
        services[eco_service] = float("{:.5g}".format(factor_final))

    return services


def compute_animal_ecosystemic_services(
    food_metadata,
    ecs_for_activities,
    metadata_by_alias,
    ecosystemic_factors,
    feed_file_content,
    ugb,
) -> dict:
    services = {}

    alias = food_metadata["alias"]
    feed_quantities = feed_file_content[alias]

    hedges = 0
    plotSize = 0
    cropDiversity = 0

    # Go through each dependency of the animal
    for feed_activity_alias, quantity in feed_quantities.items():
        # We don't have the ecs for the corresponding vegetable, so we need to compute it
        if feed_activity_alias not in ecs_for_activities:
            if feed_activity_alias not in metadata_by_alias:
                raise ValueError(
                    f"-> {feed_activity_alias} not in activities list, can't compute ecs"
                )

            feed_activity_services = compute_vegetal_ecosystemic_services(
                metadata_by_alias[feed_activity_alias],
                ecosystemic_factors,
            )
            ecs_for_activities[feed_activity_alias] = feed_activity_services

        feed_services = ecs_for_activities[feed_activity_alias]
        hedges += quantity * feed_services["hedges"]
        plotSize += quantity * feed_services["plotSize"]
        cropDiversity += quantity * feed_services["cropDiversity"]

    services["hedges"] = hedges
    services["plotSize"] = plotSize
    services["cropDiversity"] = cropDiversity

    services["permanentPasture"] = feed_quantities.get(
        "grazed-grass-permanent",  # Using alias instead of UUID
        0,
    )

    services["livestockDensity"] = compute_livestock_density_ecosystemic_service(
        food_metadata, ugb, ecosystemic_factors
    )

    ecs_for_activities[alias] = services

    return ecs_for_activities


def activities_to_ingredients_json(
    activities: List[dict],
    ingredients_paths: List[str],
    ecosystemic_factors_path: str,
    feed_file_path: str,
    ugb_file_path: str,
    cpu_count: int,
) -> List[dict]:
    ecosystemic_factors = load_ecosystemic_dic(ecosystemic_factors_path)

    feed_file_content = {}

    with open(feed_file_path, "r") as file:
        feed_file_content = json.load(file)

    ugb = load_ugb_dic(ugb_file_path)

    activities_with_land_occupation = add_land_occupations(activities, cpu_count)

    ingredients = activities_to_ingredients(
        activities_with_land_occupation, ecosystemic_factors, feed_file_content, ugb
    )

    ingredients_dicts = [
        ingredient.model_dump(by_alias=True, exclude_none=True)
        for ingredient in ingredients
    ]

    ingredients_dicts.sort(key=lambda x: x["id"])

    exported_files = []
    for ingredients_path in ingredients_paths:
        export_json(ingredients_dicts, ingredients_path)

        exported_files.append(ingredients_path)

    for ingredients_path in exported_files:
        logger.debug(
            f"-> Exported {len(ingredients_dicts)} 'ingredients' to {ingredients_path}"
        )

    return ingredients_dicts


def add_land_occupation(activity: dict) -> dict:
    """Add land occupation data to a food activity.

    If the activity already has hardcoded land occupation values in its metadata,
    those values are preserved. Otherwise, the land occupation is computed using
    Brightway data.

    Note: Hardcoded values are used when Brightway results differ significantly
    from SimaPro calculations.

    Land occupation is supposed to be specific to the source
    and activityName, so the same value should applies to all metadata entries for an activity.

    But in some cases we want to impose different values to differentiate ingredients, example : walnut-inshell-fr

    Args:
        activity: A dictionary representing a food activity with metadata

    Returns:
        The activity dictionary with land occupation data added to food metadata
    """
    land_occupation = None

    for food_metadata in activity["metadata"]["food"]:
        hardcoded = food_metadata.get("landOccupation")
        if hardcoded:
            logger.debug(
                f"-> Not computing land occupation for {food_metadata['alias']}, value is already hardcoded"
            )
        else:
            if not land_occupation:
                land_occupation = compute_land_occupation(
                    cached_search_one(
                        activity.get("source"),
                        activity.get("activityName"),
                        location=activity.get("location"),
                    )
                )
            food_metadata["landOccupation"] = land_occupation

    return activity


def add_land_occupations(activities: List[dict], cpu_count) -> List[dict]:
    with Pool(cpu_count) as pool:
        return pool.map(add_land_occupation, activities)


def activities_to_ingredients(
    activities: List[dict], ecosystemic_factors, feed_file_content, ugb
) -> List[Ingredient]:
    ecs_by_alias = compute_ecs_for_activities(
        activities, ecosystemic_factors, feed_file_content, ugb
    )

    ingredients = []
    for activity in activities:
        ingredients.extend(activity_to_ingredients(activity, ecs_by_alias))

    return ingredients


def activity_to_ingredients(eco_activity: dict, ecs_by_alias: dict) -> List[Ingredient]:
    ingredients = []

    bw_activity = cached_search_one(
        eco_activity.get("source"),
        eco_activity.get("activityName"),
        location=eco_activity.get("location"),
    )

    for food_metadata in eco_activity["metadata"]["food"]:
        land_occupation = food_metadata.get("landOccupation")

        ecosystemic_services = None

        ecs = ecs_by_alias.get(food_metadata["alias"])

        if ecs:
            ecosystemic_services = EcosystemicServices(
                crop_diversity=ecs.get("cropDiversity"),
                hedges=ecs.get("hedges"),
                livestock_density=ecs.get("livestockDensity"),
                permanent_pasture=ecs.get("permanentPasture"),
                plot_size=ecs.get("plotSize"),
            )

        ingredients.append(
            Ingredient(
                alias=food_metadata["alias"],
                categories=food_metadata.get("ingredientCategories", []),
                crop_group=food_metadata.get("cropGroup"),
                default_origin=food_metadata["defaultOrigin"],
                density=food_metadata["ingredientDensity"],
                ecosystemic_services=ecosystemic_services,
                id=food_metadata["id"],
                inedible_part=food_metadata["inediblePart"],
                land_occupation=land_occupation,
                location=bw_activity.get("location"),
                name=food_metadata["displayName"],
                raw_to_cooked_ratio=food_metadata["rawToCookedRatio"],
                scenario=food_metadata.get("scenario"),
                activity_name=eco_activity["activityName"],
                transport_cooling=food_metadata["transportCooling"],
                visible=food_metadata["visible"],
                process_id=get_process_id(eco_activity, bw_activity),
            )
        )
    return ingredients


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


def scenario(activity):
    """compute scenario from activity data
    (if missing)"""
    if "ingredient" not in activity["categories"]:
        return None
    if "scenario" in activity:
        return activity["scenario"]
    if (
        "organic" in activity["ingredientCategories"]
        or "organic" in activity.get("activityName", "").lower()
    ):
        return "organic"
    match activity["defaultOrigin"]:
        case DefaultOrigin.FRANCE:
            return Scenario.REFERENCE
        case DefaultOrigin.EUROPE_AND_MAGHREB:
            return Scenario.IMPORT
        case (
            DefaultOrigin.OUT_OF_EUROPE_AND_MAGHREB
            | DefaultOrigin.OUT_OF_EUROPE_AND_MAGHREB_BY_PLANE
        ):
            return Scenario.IMPORT
