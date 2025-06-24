#!/usr/bin/env python3
"""
Tests to validate UUIDs in json files.
"""

import uuid
from pathlib import Path
from typing import Dict, List, Tuple

from common.export import load_json

FILES = [
    "activities_to_create.json",
    "activities.json",
    "tests/activities_to_create.json",
    "tests/fixtures/activities.json",
    "public/data/food/ingredients.json",
    "public/data/processes.json",
    # for now textile materials don't have uuid
    # "public/data/textile/materials.json",
]


def validate_uuids(
    activities: List[Dict],
) -> Tuple[List[str], List[str], List[str]]:
    """
    Validate UUIDs in activities.

    Returns:
        Tuple of (missing_uuids, invalid_uuids, duplicate_uuids)
    """
    missing_uuids = []
    invalid_uuids = []
    seen_uuids = set()
    duplicate_uuids = []

    for i, activity in enumerate(activities):
        activity_name = activity.get("alias", activity.get("newName", f"Activity {i}"))

        # Check if UUID exists
        if "id" not in activity or not activity["id"]:
            missing_uuids.append(f"{activity_name} (index {i})")
            continue

        # Check if UUID is valid
        try:
            uuid_obj = uuid.UUID(activity["id"])
            uuid_str = str(uuid_obj)
        except ValueError:
            invalid_uuids.append(f"{activity_name} (index {i}): {activity['id']}")
            continue

        # Check for duplicates
        if uuid_str in seen_uuids:
            duplicate_uuids.append(f"{activity_name} (index {i}): {uuid_str}")
        else:
            seen_uuids.add(uuid_str)

    return missing_uuids, invalid_uuids, duplicate_uuids


def test_all_json_files():
    """Test all  files in the project"""

    for file_path in FILES:
        if Path(file_path).exists():
            print(f"\nTesting {file_path}...")
            activities = load_json(file_path)
            missing_uuids, invalid_uuids, duplicate_uuids = validate_uuids(activities)

            assert not missing_uuids, f"Missing UUIDs in {file_path}:\n" + "\n".join(
                missing_uuids
            )
            assert not invalid_uuids, f"Invalid UUIDs in {file_path}:\n" + "\n".join(
                invalid_uuids
            )
            assert not duplicate_uuids, (
                f"Duplicate UUIDs in {file_path}:\n" + "\n".join(duplicate_uuids)
            )

            if missing_uuids:
                print(f"❌ Missing UUIDs in {file_path}:")
                for missing in missing_uuids:
                    print(f"  - {missing}")

            if invalid_uuids:
                print(f"❌ Invalid UUIDs in {file_path}:")
                for invalid in invalid_uuids:
                    print(f"  - {invalid}")

            if duplicate_uuids:
                print(f"❌ Duplicate UUIDs in {file_path}:")
                for duplicate in duplicate_uuids:
                    print(f"  - {duplicate}")

            if not missing_uuids and not invalid_uuids and not duplicate_uuids:
                print(
                    f"✓ All {len(activities)} activities in {file_path} have valid and unique UUIDs"
                )


if __name__ == "__main__":
    print("Running UUID validation tests...")

    try:
        test_all_json_files()
        print("\n🎉 All UUID validation tests passed!")
    except AssertionError as e:
        print(f"\n❌ Test failed: {e}")
        exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error: {e}")
        exit(1)
