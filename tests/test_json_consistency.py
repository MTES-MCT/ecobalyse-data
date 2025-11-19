#!/usr/bin/env python3
"""
Consistency checks on json files.
To add a new check define a new function and set it in the CHECKS dict
"""

import json
import uuid
from collections import Counter

from ecobalyse_data.export.food import Scenario, scenario


def duplicate(filename, content, key):
    "Duplicate check"
    values = [act[key] for act in content if key in act]
    counter = Counter(values)
    duplicates = [name for name, count in counter.items() if count > 1 and name]
    if duplicates:
        raise AssertionError(f"Duplicate {key} in {filename}: " + ", ".join(duplicates))


def consistent_metadata(filename, content):
    """
    Check that metadata and scope are consistent in activities.json
    - an activity can have a scope and no metadata for that scope (metadata is optional)
    - but an activity can't have metadata for scopeA and not have scopeA in activity["scopes"]
    """
    for object in content:
        metadata = object.get("metadata")
        if metadata:
            metadata_keys = set(metadata.keys())
            scopes = set(object["scopes"])
            if not metadata_keys <= scopes:  # metadata_keys must be a subset of scopes
                extra_metadata = metadata_keys - scopes
                raise AssertionError(
                    f"Inconsistent metadata-scopes for object {object['displayName']} in {filename}: metadata keys {extra_metadata} not in scopes {scopes}"
                )


def invalid_uuid(filename, content, key):
    "Invalid UUID check"
    invalid_uuids = []
    for obj in content:
        try:
            uuid.UUID(obj.get(key))
        except ValueError:
            invalid_uuids.append(f"Invalid UUID: '{obj[key]}' in {filename}\n")
            continue
        except TypeError:
            invalid_uuids.append(f"Missing UUID in {filename}: {obj}\n")
            continue

    if invalid_uuids:
        raise AssertionError("".join(invalid_uuids))


def missing(filename, content, key):
    "Missing check"
    missing_items = []
    for obj in content:
        if key not in obj or not obj[key]:
            missing_items.append(f"Missing '{key}' in {filename}:")
            missing_items.append(f"    {obj}")

    if missing_items:
        raise AssertionError("\n".join(missing_items))


def check_ingredient_densities(filename, content, key):
    """check the ingredientDensity is strictly positive"""
    wrong = []
    for obj in content:
        if "ingredient" in obj.get("categories"):
            for metadata in obj["metadata"]["food"]:
                if metadata.get("ingredientDensity", 0) <= 0:
                    wrong.append(
                        f"Wrong or missing '{key}' for `{obj['displayName']}` in {filename}"
                    )

    if wrong:
        raise AssertionError("\n".join(wrong))


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
            errors.append(f"No scenario found for `{obj['displayName']}` in {filename}")
        else:
            if obj["scenario"] not in list(Scenario):
                errors.append(
                    f"Wrong scenario: `{obj['scenario']}` for `{obj['displayName']}`"
                )
            if obj.get("scenario") != scenario(obj):
                errors.append(
                    f"Wrong scenario for `{obj['displayName']}` in {filename}"
                )
        # organic scenario is kind of redundant with organic category
        # but check it anyway
        if (
            scenario(obj) == Scenario.ORGANIC
            and "organic" not in obj["ingredientCategories"]
        ):
            errors.append(
                f"The 'ingredientCategories' should contain 'organic' for `{obj['displayName']}` in {filename}"
            )

    if errors:
        raise AssertionError("\n".join(errors))


def check_all(checks_by_file, content_checks_by_file=None):
    for filename, checks_by_key in checks_by_file.items():
        print(f"Checking {filename}")
        with open(filename) as f:
            content = json.load(f)

            # Run content-level checks (no specific key)
            if content_checks_by_file and filename in content_checks_by_file:
                for function in content_checks_by_file[filename]:
                    function(filename, content)
                    print("  OK: " + function.__doc__)

            # Run key-specific checks
            for key, checks in checks_by_key.items():
                for function in checks:
                    function(filename, content, key)
                    print("  OK: " + function.__doc__ + f" for key '{key}'")
    print("== All checks passed ==")


# Key-specific checks: validate specific fields
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
        "displayName": (duplicate,),
        "alias": (duplicate,),
    },
    "public/data/food/ingredients.json": {
        "id": (duplicate, invalid_uuid, missing),
        "alias": (missing, duplicate),
        "name": (missing, duplicate),
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

# Content-level checks: validate relationships across the entire content
CONTENT_CHECKS = {
    "activities.json": (consistent_metadata,),
}


def test():
    check_all(CHECKS, CONTENT_CHECKS)


if __name__ == "__main__":
    print("Running consistency tests on json files...")

    try:
        check_all(CHECKS, CONTENT_CHECKS)
        print("\n🎉 All checks have passed!")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        exit(1)
