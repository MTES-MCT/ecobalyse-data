#!/usr/bin/env -S uv run --script
"""
Transform activities.json from flat structure to nested structure with metadata.
"""

import json
import sys
from collections import defaultdict
from typing import Any, Dict, List

# Base Process fields that stay at the top level
BASE_PROCESS_FIELDS = {
    "activityName",
    "alias",
    "categories",
    "comment",
    "density",
    "displayName",
    "elecMJ",
    "heatMJ",
    "impacts",
    "location",
    "scopes",
    "source",
    "unit",
    "waste",
}

# Food-specific fields (Ingredient model)
FOOD_SPECIFIC_FIELDS = {
    "alias",  # Can overload base alias
    "animalGroup1",
    "animalGroup2",
    "animalProduct",
    "cropGroup",
    "defaultOrigin",
    "displayName",  # Can overload base displayName
    "ecosystemicServices",
    "id",  # Original ingredient ID (different from process ID)
    "inediblePart",
    "ingredientCategories",
    "ingredientDensity",
    "landOccupation",
    "rawToCookedRatio",
    "scenario",
    "transportCooling",
    "visible",
    "explain",
}

# Textile/Material-specific fields (Material model)
TEXTILE_MATERIAL_SPECIFIC_FIELDS = {
    "alias",  # Can overload base alias
    "cff",
    "defaultCountry",
    "displayName",  # Can overload base displayName
    "geographicOrigin",
    "id",  # Original material ID (different from process ID)
    "origin",
    "primary",
    "recycledFrom",
    "materialName",
    "name",
}


def get_scope_specific_fields(activity: Dict[str, Any]) -> Dict[str, Dict[str, Any]]:
    """Extract scope-specific fields from an activity."""
    scopes = activity.get("scopes", [])
    scope_fields = defaultdict(dict)

    # Fields that can appear in both base and metadata
    OVERLOADABLE_FIELDS = {"displayName", "alias"}

    # Determine which fields are scope-specific
    for key, value in activity.items():
        if key in BASE_PROCESS_FIELDS and key not in OVERLOADABLE_FIELDS:
            continue

        if "food" in scopes and key in FOOD_SPECIFIC_FIELDS:
            scope_fields["food"][key] = value
        elif (
            any(scope in scopes for scope in ["textile", "object"])
            and key in TEXTILE_MATERIAL_SPECIFIC_FIELDS
        ):
            # For textile/object, use the first matching scope
            for scope in ["textile", "object"]:
                if scope in scopes:
                    scope_fields[scope][key] = value
                    break

    return scope_fields


def has_real_scope_specific_fields(scope_fields: Dict[str, Any]) -> bool:
    """
    Check if there are real scope-specific fields beyond just alias, displayName, and id.

    Only create metadata if there are actual scope-specific fields like transportCooling,
    defaultCountry, etc.
    """
    # Fields that are not enough by themselves to warrant metadata
    MINIMAL_FIELDS = {"alias", "displayName", "id"}

    # Check if there are any fields beyond the minimal ones
    for field in scope_fields.keys():
        if field not in MINIMAL_FIELDS:
            return True

    return False


def transform_activity(activity: Dict[str, Any]) -> Dict[str, Any]:
    """Transform a single activity to the new format."""
    base_object = {}

    # Extract base Process fields
    for field in BASE_PROCESS_FIELDS:
        if field in activity:
            base_object[field] = activity[field]

    # Get scope-specific fields
    scope_fields = get_scope_specific_fields(activity)

    # Only add metadata if there are real scope-specific fields
    if scope_fields:
        metadata = {}
        for scope, fields in scope_fields.items():
            # Only add this scope if it has real scope-specific fields
            if fields and has_real_scope_specific_fields(fields):
                # Create a list with single entry for now
                # (grouping will be done in the next step)
                metadata[scope] = [fields]

        if metadata:
            base_object["metadata"] = metadata

    return base_object


def group_activities_by_process(
    activities: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """
    Group activities that share the same process (same activityName, source, and location or displayName).

    For activities with the same underlying process but different metadata
    (different ingredients using the same process), group them together.
    """
    # First pass: group by activityName + source + location
    groups = defaultdict(list)

    for activity in activities:
        # Use activityName, source, and location as the grouping key
        activity_name = activity.get("activityName", "")

        # If no activityName, don't group - give each a unique key
        if not activity_name:
            key = activity["displayName"]
        else:
            key = (
                activity_name,
                activity.get("source", ""),
                activity.get("location", ""),
            )

        groups[key].append(activity)

    # Second pass: create final structure
    result = []

    for group in groups.values():
        if len(group) == 1:
            # Single activity, no grouping needed
            result.append(transform_activity(group[0]))
        else:
            # Multiple activities sharing the same process
            # Create base object from first activity
            base = {}
            first_activity = group[0]

            for field in BASE_PROCESS_FIELDS:
                if field in first_activity:
                    base[field] = first_activity[field]

            # Collect all metadata entries
            metadata = defaultdict(list)

            for activity in group:
                scope_fields = get_scope_specific_fields(activity)
                for scope, fields in scope_fields.items():
                    # Only add if there are real scope-specific fields
                    if fields and has_real_scope_specific_fields(fields):
                        metadata[scope].append(fields)

            if metadata:
                base["metadata"] = dict(metadata)

            result.append(base)

    return result


def main():
    # Parse command-line arguments
    if len(sys.argv) == 3:
        input_file = sys.argv[1]
        output_file = sys.argv[2]
    elif len(sys.argv) == 1:
        # Default values for backward compatibility
        input_file = "activities_old.json"
        output_file = "activities_transformed.json"
    else:
        print("Usage: python script.py [input_file] [output_file]")
        print("  or: python script.py (uses default files)")
        sys.exit(1)

    with open(input_file, "r", encoding="utf-8") as f:
        activities = json.load(f)

    print(f"Found {len(activities)} activities")

    print("Transforming activities...")
    transformed = group_activities_by_process(activities)

    print(
        f"Created {len(transformed)} activities (some may have multiple metadata entries)"
    )

    print(f"Writing to {output_file}...")
    with open(output_file, "w", encoding="utf-8") as f:
        json.dump(transformed, f, indent=2, ensure_ascii=False)

    print("Done!")

    with_metadata = sum(1 for a in transformed if "metadata" in a)
    print("\nStatistics:")
    print(f"  Total activities: {len(transformed)}")
    print(f"  Activities with metadata: {with_metadata}")
    print(f"  activities without metadata: {len(transformed) - with_metadata}")


if __name__ == "__main__":
    main()
