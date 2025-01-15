#!/usr/bin/env python3
import os

import bw2data

from common import brightway_patch as brightway_patch
from common.import_ import add_created_activities

if __name__ == "__main__":
    """Add additional processes"""

    bw2data.projects.set_current("ecobalyse")
    # if "Ecobalyse" in bw2data.databases:
    #     del bw2data.databases["Ecobalyse"]

    if (db := "Ecobalyse") not in bw2data.databases:
        for vertical in ("food", "textile", "object"):
            file = f"{vertical}/activities_to_create.json"
            if os.path.exists(file):
                add_created_activities(db, file)
    else:
        print(f"{db} already imported")
