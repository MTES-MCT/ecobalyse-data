#!/usr/bin/env python3


import os
from os.path import join

import bw2data
import bw2io

from common import brightway_patch as brightway_patch
from common.import_ import add_missing_substances, import_simapro_csv

CURRENT_FILE_DIR = os.path.dirname(os.path.realpath(__file__))

DB_FILES_DIR = os.getenv(
    "DB_FILES_DIR",
    os.path.join(CURRENT_FILE_DIR, "..", "dbfiles"),
)

# Ecoinvent
EI391 = "./Ecoinvent3.9.1.CSV.zip"
EI310 = "./Ecoinvent3.10.CSV.zip"
WOOL = "./wool.CSV.zip"
BIOSPHERE = "biosphere3"
PROJECT = "ecobalyse"
EXCLUDED = [
    "fix_localized_water_flows",  # both agb and ef31 adapted have localized wf
    "simapro-water",
]


# Patch for https://github.com/brightway-lca/brightway2-io/pull/283
def lower_formula_parameters(db):
    """add irrigation to the organic cotton"""
    for ds in db:
        for k in ds.get("parameters", {}).keys():
            if "formula" in ds["parameters"][k]:
                ds["parameters"][k]["formula"] = ds["parameters"][k]["formula"].lower()
    return db


def organic_cotton_irrigation(db):
    """add irrigation to the organic cotton"""
    for ds in db:
        if ds.get("simapro metadata", {}).get("Process identifier") in (
            "MTE00149000081182217968",  # EI 3.9.1
            "EI3ARUNI000011519618166",  # EI 3.10
        ):
            # add: irrigation//[IN] market for irrigation;m3;0.75;Undefined;0;0;0;;
            ds["exchanges"].append(
                {
                    "amount": 0.75,
                    "categories": ("Materials/fuels",),
                    "comment": "",
                    "loc": 0.75,
                    "name": "irrigation//[IN] market for irrigation",
                    "negative": False,
                    "type": "technosphere",
                    "uncertainty type": 2,
                    "unit": "cubic meter",
                }
            )
    return db


STRATEGIES = [organic_cotton_irrigation]


def main():
    print("bw2io version", bw2io.__version__)
    print("bw2data version", bw2data.__version__)
    print("projects", bw2data.projects)

    if PROJECT not in bw2data.projects:
        bw2io.remote.install_project("ecoinvent-3.9.1-biosphere", "ecobalyse")

    bw2data.projects.set_current(PROJECT)

    add_missing_substances(PROJECT, BIOSPHERE)

    if (db := "Ecoinvent 3.9.1") not in bw2data.databases:
        import_simapro_csv(
            join(DB_FILES_DIR, EI391),
            db,
            first_strategies=STRATEGIES,
            excluded_strategies=EXCLUDED,
        )
    else:
        print(f"{db} already imported")

    if (db := "Ecoinvent 3.10") not in bw2data.databases:
        import_simapro_csv(
            join(DB_FILES_DIR, EI310),
            db,
            first_strategies=STRATEGIES,
            excluded_strategies=EXCLUDED,
        )

    else:
        print(f"{db} already imported")

    if (db := "Woolmark") not in bw2data.databases:
        import_simapro_csv(
            join(DB_FILES_DIR, WOOL),
            db,
            external_db="Ecoinvent 3.10",  # wool is linked with EI 3.10
            first_strategies=[lower_formula_parameters],
            excluded_strategies=EXCLUDED,
        )
    else:
        print(f"{db} already imported")


if __name__ == "__main__":
    main()
