#!/usr/bin/env -S uv run --script
"""
Transform activities.json from flat structure to nested structure with metadata.
"""

import json
import uuid


def main():
    activities_file = "./activities.json"
    activities = None
    with open(activities_file, "r", encoding="utf-8") as f:
        activities = json.load(f)

        for activity in activities:
            if "food" in activity["scopes"] and "food2" not in activity["scopes"]:
                activity["scopes"].append("food2")

                if activity.get("metadata"):
                    md_scope_added = False
                    for m in activity["metadata"]:
                        if "food" in m["scopes"]:
                            m["scopes"].append("food2")
                            md_scope_added = True
                    if not md_scope_added:
                        activity["metadata"][0]["scopes"].append("food2")
                        md_scope_added = True

                else:
                    activity["metadata"] = [
                        {
                            "id": str(uuid.uuid4()),
                            "scopes": ["food2"],
                        }
                    ]

    print(f"Writing to {activities_file}...")
    with open(activities_file, "w", encoding="utf-8") as f:
        json.dump(activities, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
