#!/usr/bin/env -S uv run --script
"""
Explode the activities.json file to a `lci_catalog/<source>/<alias>.json` tree
"""

import json
import re
import unicodedata
from pathlib import Path

BASE_PATH = Path(__file__).parent.parent


# Adapted from https://github.com/django/django/blob/main/django/utils/text.py
def slugify(value):
    """
    Convert spaces or repeated dashes to single dashes. Remove characters that
    aren't alphanumerics, underscores, dots or hyphens. Convert to lowercase.
    Also strip leading and trailing whitespace, dashes, underscores and dots.
    """
    value = str(value)
    value = (
        unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    )
    value = re.sub(r"[^\w^\.\s-]", "", value.lower())
    return re.sub(r"[-.\s]+", "-", value).strip("-_")


def explode(activities_file, activities_root):
    Path.mkdir(activities_root, exist_ok=True)
    activities = None
    with open(activities_file, "r", encoding="utf-8") as f:
        activities = json.load(f)

        for activity in activities:
            source_dir = activities_root / slugify(activity["source"])
            Path.mkdir(source_dir, exist_ok=True)
            with open(
                (source_dir / activity["alias"]).with_suffix(".json"),
                "w",
                encoding="utf-8",
            ) as f:
                del activity["alias"]
                json.dump(activity, f, indent=2, ensure_ascii=False)


def main():
    explode(BASE_PATH / "activities.json", BASE_PATH / "lci_catalog")
    explode(
        BASE_PATH / "tests" / "fixtures" / "activities.json",
        BASE_PATH / "tests" / "fixtures" / "lci_catalog",
    )


if __name__ == "__main__":
    main()
