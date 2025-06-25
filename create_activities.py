#!/usr/bin/env python3
import os

import bw2data

from common import brightway_patch as brightway_patch
from common.import_ import add_created_activities, setup_project


def create_activities(file):
    """Add additional processes"""

    if "Ecobalyse" in bw2data.databases:
        del bw2data.databases["Ecobalyse"]

    if (dbname := "Ecobalyse") not in bw2data.databases:
        if os.path.exists(file):
            print(f"Adding activities from {file} to {dbname}")  # Add this line
            add_created_activities(dbname, file)
        else:
            print(f"File {file} does not exist")
    else:
        print(f"{dbname} already imported")


if __name__ == "__main__":
    setup_project()
    create_activities("activities_to_create.json")
