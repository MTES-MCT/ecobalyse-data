#!/usr/bin/env python3
"""
Consistency checks on json files.
To add a new check define a new function and set it in the CHECKS dict
"""

import json
import uuid
from collections import Counter

from ecobalyse_data.export.food import Scenario, scenario


# validation functions, which should just return a string if any error
def duplicate(filename, content, key):
    "Duplicate check"
    values = [act[key] for act in content if key in act]
    counter = Counter(values)
    duplicates = [name for name, count in counter.items() if count > 1 and name]
    if duplicates:
        return f"❌ Duplicate {key} in {filename}: " + ", ".join(duplicates)


def invalid_uuid(filename, content, key):
    "Invalid UUID check"
    invalid_uuids = []
    for obj in content:
        try:
            uuid.UUID(obj.get(key))
        except ValueError:
            invalid_uuids.append(f"❌ Invalid UUID: '{obj[key]}' in {filename}\n")
            continue
        except TypeError:
            invalid_uuids.append(f"❌ Missing UUID in {filename}: {obj}\n")
            continue
    return "".join(invalid_uuids)


def missing(filename, content, key):
    "Missing check"
    missing = set()
    for obj in content:
        if key not in obj or not obj[key]:
            missing.add(f"❌ Missing '{key}' in {filename}:")
            missing.add(f"    {obj}")
    return missing


def check_ingredient_densities(filename, content, key):
    """check the ingredientDensity is strictly positive"""
    wrong = []
    for obj in content:
        if "ingredient" in obj.get("categories"):
            for metadata in obj["metadata"]["food"]:
                if metadata.get("ingredientDensity", 0) <= 0:
                    wrong.append(
                        f"❌ Wrong or missing '{key}' for `{obj['displayName']}` in {filename}:"
                    )
    return wrong


def check_scenario(filename, content, key):
    """Check scenario consistency"""
    errors = []
    for obj in content:
        if "ingredient" not in obj["categories"]:
            continue
        if not obj.get("ingredientCategories"):
            continue
        # scenario must be there and
        # computed scenario must be the same as stored scenario
        # (at least for now)
        if "scenario" not in obj:
            errors.append(
                f"❌ No scenario found for `{obj['displayName']}` in {filename}"
            )
        else:
            if obj["scenario"] not in list(Scenario):
                errors.append(
                    f"❌ Wrong scenario: `{obj['scenario']}` for `{obj['displayName']}`"
                )
            if obj.get("scenario") != scenario(obj):
                errors.append(
                    f"❌ Wrong scenario for `{obj['displayName']}` in {filename}"
                )
        # organic scenario is kind of redundant with organic category
        # but check it anyway
        if (
            scenario(obj) == Scenario.ORGANIC
            and "organic" not in obj["ingredientCategories"]
        ):
            errors.append(
                f"❌ The 'ingredientCategories' should contain 'organic' for `{obj['displayName']}` in {filename}"
            )

    return "\n".join(errors)


def check_all(checks_by_file):
    for filename, checks_by_key in checks_by_file.items():
        print(f"Checking {filename}")
        with open(filename) as f:
            content = json.load(f)
            for key, checks in checks_by_key.items():
                for function in checks:
                    error = function(filename, content, key)
                    if error:
                        error_context = f"\n{'=' * 80}\nFailed check : {function.__doc__} for key '{key}'\nFile: {filename}\n{'=' * 80}\n{error}"
                        assert False, error_context

                    print("  OK: " + function.__doc__ + f" for key '{key}'")
    print("== All checks passed ==")


CHECKS = {
    "activities_to_create.json": {
        "id": (duplicate, invalid_uuid, missing),
        "alias": (duplicate,),
        "newName": (duplicate, missing),
    },
    "activities.json": {
        "displayName": (duplicate,),
        "alias": (duplicate,),
        "scenario": (check_scenario,),
        "ingredientDensity": (check_ingredient_densities,),
    },
    "tests/activities_to_create.json": {
        "id": (duplicate, invalid_uuid, missing),
        "alias": (duplicate,),
        "newName": (duplicate, missing),
    },
    "tests/fixtures/activities.json": {
        "id": (duplicate, invalid_uuid),
        "displayName": (duplicate,),
        "alias": (duplicate,),
    },
    "public/data/food/ingredients.json": {
        "id": (duplicate, invalid_uuid, missing),
        "alias": (missing,),
        "name": (missing, duplicate),
        "displayName": (missing, duplicate),
    },
    "public/data/processes.json": {
        "id": (duplicate, invalid_uuid, missing),
        "displayName": (duplicate,),
    },
    "public/data/textile/materials.json": {
        "id": (duplicate, missing),
        "name": (missing,),
        "processId": (missing, duplicate, invalid_uuid),
    },
}


def test():
    check_all(CHECKS)


if __name__ == "__main__":
    print("Running consistency tests on json files...")

    try:
        check_all(CHECKS)
        print("\n🎉 All checks have passed!")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        exit(1)
