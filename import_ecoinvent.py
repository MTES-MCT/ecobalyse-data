#!/usr/bin/env python3


import os
from os.path import join

import bw2data

from common import brightway_patch as brightway_patch
from common.import_ import (
    DB_FILES_DIR,
    import_simapro_block_csv,
    setup_project,
)

CURRENT_FILE_DIR = os.path.dirname(os.path.realpath(__file__))

# Ecoinvent
EI391 = "./Ecoinvent3.9.1.CSV.zip"
EI391_CSV = "./Ecoinvent3.9.1.CSV"
EI310 = "./Ecoinvent3.10.CSV.zip"
EI310_CSV = "./Ecoinvent3.10.CSV"
WOOL = "./wool.CSV.zip"
WOOL_CSV = "./wool.CSV"
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
    setup_project()

    # Time: 1m34s
    if (db := "Ecoinvent 3.9.1 new import") not in bw2data.databases:
        import_simapro_block_csv(
            join(DB_FILES_DIR, EI391_CSV),
            db,
            first_strategies=STRATEGIES,
            excluded_strategies=EXCLUDED,
        )
    else:
        print(f"{db} already imported")

    # if (db := "Ecoinvent 3.9.1") not in bw2data.databases:
    #     import_simapro_csv(
    #         join(DB_FILES_DIR, EI391_CSV),
    #         db,
    #         first_strategies=STRATEGIES,
    #         excluded_strategies=EXCLUDED,
    #     )
    # else:
    #     print(f"{db} already imported")

    if (db := "Ecoinvent 3.10") not in bw2data.databases:
        import_simapro_block_csv(
            join(DB_FILES_DIR, EI310_CSV),
            db,
            first_strategies=STRATEGIES,
            excluded_strategies=EXCLUDED,
        )

    else:
        print(f"{db} already imported")

    if (db := "Woolmark") not in bw2data.databases:
        import_simapro_block_csv(
            join(DB_FILES_DIR, WOOL_CSV),
            db,
            external_db="Ecoinvent 3.10",  # wool is linked with EI 3.10
            first_strategies=[lower_formula_parameters],
            excluded_strategies=EXCLUDED,
        )
    else:
        print(f"{db} already imported")


if __name__ == "__main__":
    main()
