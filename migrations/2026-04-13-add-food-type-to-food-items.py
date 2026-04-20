#!/usr/bin/env -S uv run --script
"""
Transform activities.json from flat structure to nested structure with metadata.
"""

import json

# Extracted from https://fabrique-numerique.gitbook.io/ecobalyse/alimentaire/impacts-consideres/rapport-cru-cuit
RATIO_TO_CAT = {
    0.856: "material_type:fruits_and_vegetables",
    0.819: "material_type:fish_and_shellfish",
    2.259: None,  # Cereals
    2.330: None,  # Legumes
    0.974: "material_type:eggs",
    0.792: "material_type:red_meats",
    0.755: "material_type:poultry",
    0.730: "material_type:offal",
}


def main():
    activities_file = "./activities.json"
    activities = None
    with open(activities_file, "r", encoding="utf-8") as f:
        activities = json.load(f)

        for activity in activities:
            if "ingredient" in activity["categories"]:
                md = activity["metadata"]
                if not len(md):
                    continue
                rawToCookedRatio = md[0]["rawToCookedRatio"]

                if any([m["rawToCookedRatio"] != rawToCookedRatio for m in md]):
                    print(
                        f"{activity['displayName']}: ⚠️ several rawToCookedRatio found, using the first one – {[m['alias'] for m in md]} {[m['rawToCookedRatio'] for m in md]}",
                    )
                else:
                    if RATIO_TO_CAT.get(rawToCookedRatio):
                        activity["categories"].append(RATIO_TO_CAT[rawToCookedRatio])
                    else:
                        if rawToCookedRatio != 2.259 and rawToCookedRatio != 2.330:
                            print(
                                f"{activity['displayName']}: no category found for ratio {rawToCookedRatio}"
                            )
                        activity["categories"].append("material_type:other_food_items")

    print(f"Writing to {activities_file}...")
    with open(activities_file, "w", encoding="utf-8") as f:
        json.dump(activities, f, indent=2, ensure_ascii=False)


if __name__ == "__main__":
    main()
