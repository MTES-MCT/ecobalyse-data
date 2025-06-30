#!/usr/bin/env python3

# from bw2io.migrations import create_core_migrations
import functools
import os
import re
from os.path import join

import bw2data
from bw2io.strategies import (
    assign_only_product_as_production,
    change_electricity_unit_mj_to_kwh,
    convert_activity_parameters_to_list,
    drop_unspecified_subcategories,
    # fix_localized_water_flows,
    fix_zero_allocation_products,
    # link_technosphere_based_on_name_unit_location,
    migrate_datasets,
    migrate_exchanges,
    normalize_biosphere_categories,
    normalize_biosphere_names,
    normalize_simapro_biosphere_categories,
    normalize_simapro_biosphere_names,
    normalize_units,
    set_code_by_activity_hash,
    sp_allocate_products,
    split_simapro_name_geo,
    strip_biosphere_exc_locations,
    update_ecoinvent_locations,
)
from bw2io.strategies.simapro import set_lognormal_loc_value_uncertainty_safe

from common import brightway_patch as brightway_patch
from common.import_ import (
    DB_FILES_DIR,
    import_simapro_csv,
    setup_project,
)
from ecobalyse_data.bw.strategy import lower_formula_parameters

CURRENT_FILE_DIR = os.path.dirname(os.path.realpath(__file__))

# Ecoinvent
EI391 = "./Ecoinvent3.9.1.CSV.zip"
WOOL = "./wool.CSV.zip"

STRATEGIES = [
    normalize_units,
    update_ecoinvent_locations,
    assign_only_product_as_production,
    drop_unspecified_subcategories,
    sp_allocate_products,
    fix_zero_allocation_products,
    split_simapro_name_geo,
    strip_biosphere_exc_locations,
    functools.partial(migrate_datasets, migration="default-units"),
    functools.partial(migrate_exchanges, migration="default-units"),
    functools.partial(set_code_by_activity_hash, overwrite=True),
    change_electricity_unit_mj_to_kwh,
    # link_technosphere_based_on_name_unit_location,  # link is done in common.import_ at the end
    set_lognormal_loc_value_uncertainty_safe,
    normalize_biosphere_categories,
    normalize_simapro_biosphere_categories,
    normalize_biosphere_names,
    normalize_simapro_biosphere_names,
    # functools.partial(migrate_exchanges, migration="simapro-water"),
    # fix_localized_water_flows,
    convert_activity_parameters_to_list,
]

WOOLMARK_MIGRATIONS = [
    {
        "name": "woolmark-units-fixes",
        "description": "Fix units",
        "data": {
            "fields": ("unit",),
            "data": [
                (
                    ("t",),
                    {"unit": "kg", "multiplier": 1000},
                ),
                (
                    ("l",),
                    {"unit": "m3", "multiplier": 0.001},
                ),
            ],
        },
    },
    {
        "name": "woolmark-technosphere",
        "description": "Process names for EI 3.9",
        "data": {
            "fields": ("name",),
            "data": [
                (
                    (
                        "Sodium bicarbonate {RoW}| market for sodium bicarbonate | Cut-off, S",
                    ),
                    {"name": "sodium bicarbonate//[GLO] market for sodium bicarbonate"},
                ),
                (
                    ("Wheat grain {AU}| market group for wheat grain | Cut-off, S",),
                    {"name": "wheat grain//[AU] wheat production"},
                ),
            ],
        },
    },
    {
        "name": "woolmark-locations",
        "description": "Remove locations to ease linking to Ecoinvent",
        "data": {
            "fields": ("location",),
            "data": [
                (("(unknown)",), {"location": None}),
            ],
        },
    },
    {
        # all commented migrations related to substances that don't exist in bw biosphere3
        # but that exist in provided EF3.1. So their substances are added anyway
        "name": "woolmark-biosphere-fixes",
        "description": "Fix substances to match biosphere3",
        "data": {
            "fields": ("name", "categories"),
            "data": [
                (
                    ("Water, fresh, AU", ("Resources", "in water")),
                    {
                        "name": "Water, river, AU",
                        "categories": ("natural resource", "in water"),
                    },
                ),
                (
                    ("Sulfate", ("Emissions to soil", "agricultural")),
                    {"categories": ("soil",)},
                ),
                (
                    ("Nitrate", ("Emissions to soil", "agricultural")),
                    {"categories": ("soil",)},
                ),
            ],
        },
    },
]


def use_unit_processes(db):
    """the woolmark dataset comes with dependent processes
    which are set as system processes.
    Ecoinvent has these processes but as unit processes.
    So we change the name so that the linking be done"""
    for ds in db:
        for exc in ds["exchanges"]:
            if exc["name"].endswith(" | Cut-off, S"):
                exc["name"] = exc["name"].replace(" | Cut-off, S", "")
                exc["name"] = re.sub(
                    r" \{([A-Za-z]{2,3})\}\| ", r"//[\1] ", exc["name"]
                )
    return db


def organic_cotton_irrigation(db):
    """add irrigation to the organic cotton to be on par with conventional"""
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


def main():
    setup_project()

    if (db := "Ecoinvent 3.9.1") not in bw2data.databases:
        import_simapro_csv(
            join(DB_FILES_DIR, EI391),
            db,
            strategies=STRATEGIES + [organic_cotton_irrigation],
        )
    else:
        print(f"{db} already imported")

    if (db := "Woolmark") not in bw2data.databases:
        import_simapro_csv(
            join(DB_FILES_DIR, WOOL),
            db,
            migrations=WOOLMARK_MIGRATIONS,
            strategies=[lower_formula_parameters] + STRATEGIES + [use_unit_processes],
            external_db="Ecoinvent 3.9.1",
        )
    else:
        print(f"{db} already imported")


if __name__ == "__main__":
    main()
