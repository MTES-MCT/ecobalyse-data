#!/usr/bin/env python3
"""
Export predicted ingredients to CSV and activities.json format.

Usage:
    python export.py                    # Export all new ingredients
    python export.py --clear-cache      # Clear translation cache first

Outputs:
    - generated/predictions.csv: CSV with all predictions and confidence scores
    - generated/new_activities.json: Activities format for Ecobalyse
"""

import argparse
import csv
import json
import re
import uuid
from pathlib import Path

import bw2data
import pandas as pd
from predict import Predictor
from rich.progress import track

bw2data.projects.set_current("ecobalyse")

# =============================================================================
# ANIMAL DETECTION
# =============================================================================

ANIMAL_PATTERNS = {
    "cattle": {
        "patterns": [r"\b(beef|boeuf|veau|veal|cattle|bovine|cow)\b"],
        "group2": "cow",
        "product_default": "meat",
    },
    "pig": {
        "patterns": [r"\b(pork|porc|pig|swine|ham|jambon|bacon|saucisse|sausage)\b"],
        "group2": "pig",
        "product_default": "meat",
    },
    "poultry": {
        "patterns": [
            r"\b(chicken|poulet|turkey|dinde|duck|canard|poultry|volaille|hen|poule)\b"
        ],
        "group2": "chicken",
        "product_default": "meat",
    },
    "sheep": {
        "patterns": [r"\b(lamb|agneau|sheep|mouton|mutton)\b"],
        "group2": "sheep",
        "product_default": "meat",
    },
}

ANIMAL_PRODUCT_PATTERNS = {
    "egg": r"\b(egg|oeuf|œuf)\b",
    "milk": r"\b(milk|lait|dairy|cheese|fromage|yogurt|yaourt|cream|crème|butter|beurre)\b",
    "meat": r"\b(meat|viande|flesh|chair)\b",
}


def detect_animal_fields(name: str, activity_name: str) -> dict:
    """Detect animalGroup1, animalGroup2, animalProduct from ingredient name."""
    text = f"{name} {activity_name}".lower()

    animal_group1 = None
    animal_group2 = None
    product_default = "meat"

    for group1, config in ANIMAL_PATTERNS.items():
        for pattern in config["patterns"]:
            if re.search(pattern, text, re.IGNORECASE):
                animal_group1 = group1
                animal_group2 = config["group2"]
                product_default = config["product_default"]
                break
        if animal_group1:
            break

    if not animal_group1:
        return {}

    animal_product = product_default
    for product, pattern in ANIMAL_PRODUCT_PATTERNS.items():
        if re.search(pattern, text, re.IGNORECASE):
            animal_product = product
            break

    return {
        "animalGroup1": animal_group1,
        "animalGroup2": animal_group2,
        "animalProduct": animal_product,
    }


# =============================================================================
# HELPERS
# =============================================================================


def generate_alias(name: str) -> str:
    """Generate alias from English name."""
    alias = name.lower()
    alias = re.sub(r"[\s_]+", "-", alias)
    alias = re.sub(r"[^a-z0-9-]", "", alias)
    alias = re.sub(r"-+", "-", alias)
    return alias.strip("-")


def load_existing_uuids(output_path: str) -> dict:
    """Load existing UUIDs from output file to preserve them on re-export."""
    existing = {}
    path = Path(output_path)
    if path.exists():
        try:
            with open(path, encoding="utf-8") as f:
                activities = json.load(f)
            for activity in activities:
                alias = activity.get("alias", "")
                activity_name = activity.get("activityName", "")
                activity_id = activity.get("id")
                ingredient_id = None
                food_list = activity.get("metadata", {}).get("food", [])
                if food_list:
                    ingredient_id = food_list[0].get("id")
                if alias and activity_id:
                    existing[(alias, activity_name)] = (activity_id, ingredient_id)
        except (json.JSONDecodeError, KeyError):
            pass
    return existing


def _format_match(match_info: dict | None) -> str:
    """Format match name for CSV output."""
    if match_info is None:
        return ""
    return match_info.get("name", "")


def _format_conf(match_info: dict | None) -> str:
    """Format confidence from match info for CSV output."""
    if match_info is None:
        return ""
    conf = match_info.get("confidence")
    return f"{conf:.3f}" if conf else ""


def get_db_unit(activity_name):
    dbs = ("Agribalyse 3.2", "Ecoinvent 3.9.1", "Ecoinvent 3.11")
    for db in dbs:
        if (
            len(
                activities := [
                    a for a in bw2data.Database(db) if a["name"] == activity_name
                ]
            )
            >= 1
        ):
            return activities[0]["unit"], db
    raise Exception(f"Not found in {str(dbs)}: {activity_name}")


def fix_unit(unit):
    return {"kilogram": "kg", "unit": "item", "litre": "L"}[unit]


# =============================================================================
# PREDICTION
# =============================================================================


def predict_all(predictor: Predictor, input_df: pd.DataFrame) -> list:
    """
    Predict metadata for all ingredients in the DataFrame.

    Returns list of dicts with: name, french_name, activity_name, source, predictions
    """
    results = []

    for _, row in track(
        input_df.iterrows(), total=len(input_df), description="Predicting..."
    ):
        name = str(row["item"]).strip()
        french_name = (
            str(row["Liste 4.1 Trad"]).strip()
            if pd.notna(row.get("Liste 4.1 Trad"))
            else ""
        )
        activity_name = (
            str(row["icv final"]).strip() if pd.notna(row["icv final"]) else ""
        )
        unit, source = get_db_unit(activity_name)

        if not name or not activity_name:
            continue

        ingredient = {"name": name, "activityName": activity_name}
        predictions = predictor.predict(ingredient)

        results.append(
            {
                "name": name,
                "french_name": french_name,
                "activity_name": activity_name,
                "source": source,
                "unit": fix_unit(unit),
                "predictions": predictions,
            }
        )

    return results


# =============================================================================
# CSV OUTPUT
# =============================================================================


def write_csv(results: list, output_path: str):
    """Write predictions to CSV file."""
    fieldnames = [
        "name",
        "categories",
        "foodType",
        "foodTypeMatch",
        "foodTypeConf",
        "processingState",
        "processingStateMatch",
        "processingStateConf",
        "transportCooling",
        "transportCoolingMatch",
        "cropGroup",
        "cropGroupMatch",
        "cropGroupConf",
        "density",
        "densityMatch",
        "densityConf",
        "inediblePart",
        "inediblePartMatch",
        "inediblePartConf",
        "rawToCookedRatio",
        "rawToCookedRatioMatch",
        "rawToCookedRatioConf",
    ]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()

        for r in results:
            pred = r["predictions"]
            categories = pred.get("categories", [])

            writer.writerow(
                {
                    "name": r["name"],
                    "categories": ",".join(categories) if categories else "",
                    "foodType": pred.get("foodType", ""),
                    "foodTypeMatch": _format_match(pred.get("foodTypeMatch")),
                    "foodTypeConf": _format_conf(pred.get("foodTypeMatch")),
                    "processingState": pred.get("processingState", ""),
                    "processingStateMatch": _format_match(
                        pred.get("processingStateMatch")
                    ),
                    "processingStateConf": _format_conf(
                        pred.get("processingStateMatch")
                    ),
                    "transportCooling": pred.get("transportCooling", ""),
                    "transportCoolingMatch": _format_match(
                        pred.get("transportCoolingMatch")
                    ),
                    "cropGroup": pred.get("cropGroup", ""),
                    "cropGroupMatch": _format_match(pred.get("cropGroupMatch")),
                    "cropGroupConf": _format_conf(pred.get("cropGroupMatch")),
                    "density": f"{pred.get('density', 0):.3f}",
                    "densityMatch": _format_match(pred.get("densityMatch")),
                    "densityConf": _format_conf(pred.get("densityMatch")),
                    "inediblePart": f"{pred.get('inediblePart', 0):.2f}",
                    "inediblePartMatch": _format_match(pred.get("inediblePartMatch")),
                    "inediblePartConf": _format_conf(pred.get("inediblePartMatch")),
                    "rawToCookedRatio": f"{pred.get('rawToCookedRatio', 0):.3f}",
                    "rawToCookedRatioMatch": _format_match(
                        pred.get("rawToCookedRatioMatch")
                    ),
                    "rawToCookedRatioConf": _format_conf(
                        pred.get("rawToCookedRatioMatch")
                    ),
                }
            )

    print(f"CSV written to {output_path}")


# =============================================================================
# JSON OUTPUT (activities.json format)
# =============================================================================


def build_activity_entry(
    name: str,
    french_name: str,
    activity_name: str,
    source: str,
    unit: str,
    predictions: dict,
    existing_uuids: dict = None,
) -> dict:
    """Build an activity entry in the activities.json format."""
    alias = generate_alias(name)

    if existing_uuids and (alias, activity_name) in existing_uuids:
        activity_id, ingredient_id = existing_uuids[(alias, activity_name)]
        if not ingredient_id:
            ingredient_id = str(uuid.uuid4())
    else:
        activity_id = str(uuid.uuid4())
        ingredient_id = str(uuid.uuid4())

    display_name = french_name if french_name else name

    ingredient = {
        "alias": alias,
        "defaultOrigin": predictions.get("defaultOrigin", "OutOfEuropeAndMaghreb"),
        "displayName": display_name,
        "id": ingredient_id,
        "inediblePart": predictions.get("inediblePart", 0),
        "inediblePartMatch": predictions.get("inediblePartMatch"),
        "ingredientCategories": predictions.get("categories", ["misc"]),
        "ingredientDensity": predictions.get("density", 1.0),
        "ingredientDensityMatch": predictions.get("densityMatch"),
        "rawToCookedRatio": predictions.get("rawToCookedRatio", 1.0),
        "rawToCookedRatioMatch": predictions.get("rawToCookedRatioMatch"),
        "scenario": "reference",
        "transportCooling": predictions.get("transportCooling", "none"),
        "transportCoolingMatch": predictions.get("transportCoolingMatch"),
        "visible": True,
    }

    if predictions.get("cropGroup"):
        ingredient["cropGroup"] = predictions["cropGroup"]
        ingredient["cropGroupMatch"] = predictions.get("cropGroupMatch")

    animal_fields = detect_animal_fields(name, activity_name)
    if animal_fields:
        ingredient["animalGroup1"] = animal_fields["animalGroup1"]
        ingredient["animalGroup2"] = animal_fields["animalGroup2"]
        ingredient["animalProduct"] = animal_fields["animalProduct"]

    return {
        "activityName": activity_name,
        "alias": alias,
        "categories": ["ingredient"],
        "displayName": display_name,
        "id": activity_id,
        "metadata": {"food": [ingredient]},
        "scopes": ["food"],
        "source": source,
        "unit": unit,
    }


def write_json(results: list, output_path: str):
    """Write activities to JSON file."""
    existing_uuids = load_existing_uuids(output_path)
    if existing_uuids:
        print(f"Loaded {len(existing_uuids)} existing UUIDs from {output_path}")

    activities = []
    for r in results:
        activity = build_activity_entry(
            r["name"],
            r["french_name"],
            r["activity_name"],
            r["source"],
            r["unit"],
            r["predictions"],
            existing_uuids,
        )
        activities.append(activity)

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(activities, f, indent=2, ensure_ascii=False)

    print(f"JSON written to {output_path}")


# =============================================================================
# CLI
# =============================================================================

INPUT_CSV = "source/new_ingredient_FR.csv"
OUTPUT_CSV = "generated/predictions.csv"
OUTPUT_JSON = "generated/new_activities.json"


def main():
    parser = argparse.ArgumentParser(
        description="Export predicted ingredients to CSV and JSON"
    )
    parser.add_argument(
        "--clear-cache",
        action="store_true",
        help="Clear translation cache before running",
    )
    args = parser.parse_args()

    if args.clear_cache:
        Predictor.clear_translation_cache()
        print("Translation cache cleared")

    # Load training data
    print("Loading training data...")
    with open("../../public/data/food/ingredients.json") as f:
        training_data = json.load(f)

    # Train predictor
    print(f"\nTraining on {len(training_data)} ingredients...")
    predictor = Predictor()
    predictor.fit(training_data)

    # Load input CSV
    print(f"\nLoading {INPUT_CSV}...")
    df = pd.read_csv(INPUT_CSV)

    if "item" not in df.columns or "icv final" not in df.columns:
        raise ValueError("CSV must have 'item' and 'icv final' columns")

    # Predict for all ingredients
    print(f"\nProcessing {len(df)} ingredients...")
    results = predict_all(predictor, df)

    # Write outputs
    print(f"\nWriting {len(results)} results...")
    write_csv(results, OUTPUT_CSV)
    write_json(results, OUTPUT_JSON)

    print("\nDone!")


if __name__ == "__main__":
    main()
