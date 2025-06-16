#!/usr/bin/env python3
import os

import bw2data

from common import brightway_patch as brightway_patch
from common.import_ import add_created_activities, setup_project

if __name__ == "__main__":
    """Add additional processes"""

    setup_project()

    if "Ecobalyse" in bw2data.databases:
        del bw2data.databases["Ecobalyse"]

    if (dbname := "Ecobalyse") not in bw2data.databases:
        file = "activities_to_create.json"
        if os.path.exists(file):
            add_created_activities(dbname, file)
    else:
        print(f"{dbname} already imported")
