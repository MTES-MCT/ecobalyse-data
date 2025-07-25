#!/usr/bin/env python3

import argparse
import copy
import functools
import os
from os.path import join

import bw2data
from bw2io.strategies import (
    assign_only_product_as_production,
    change_electricity_unit_mj_to_kwh,
    # convert_activity_parameters_to_list,
    drop_unspecified_subcategories,
    # fix_localized_water_flows,
    fix_zero_allocation_products,
    # link_technosphere_based_on_name_unit_location,
    migrate_datasets,
    migrate_exchanges,
    normalize_biosphere_categories,
    # normalize_biosphere_names,
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
    link_technosphere_by_activity_hash_ref_product,
    setup_project,
)

CURRENT_FILE_DIR = os.path.dirname(os.path.realpath(__file__))

PROJECT = "ecobalyse"
AGRIBALYSE31 = "AGB3.1.1.20230306.CSV.zip"  # Agribalyse 3.1
GINKO = "CSV_369p_et_298chapeaux_final.csv.zip"  # additional organic processes
PASTOECO = "pastoeco.CSV.zip"
CTCPA = "Export emballages_PACK AGB_CTCPA.CSV.zip"
WFLDB = "WFLDB.CSV.zip"
BIOSPHERE = "biosphere3"
ACTIVITIES = "food/activities.json"
ACTIVITIES_TO_CREATE = "food/activities_to_create.json"
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
    # link_technosphere_based_on_name_unit_location,
    set_lognormal_loc_value_uncertainty_safe,
    normalize_biosphere_categories,
    normalize_simapro_biosphere_categories,
    # normalize_biosphere_names,
    normalize_simapro_biosphere_names,
    # functools.partial(migrate_exchanges, migration="simapro-water"),
    # fix_localized_water_flows,
]
GINKO_MIGRATIONS = [
    {
        "name": "diesel-fix",
        "description": "Fix Diesel process name",
        "data": {
            "fields": ("name",),
            "data": [
                (
                    (
                        "Diesel {GLO}| market group for | Cut-off, S - Copied from ecoinvent",
                    ),
                    {
                        "name": "Diesel {GLO}| market group for | Cut-off, S - Copied from Ecoinvent U"
                    },
                ),
                (
                    (
                        "Combine harvesting {Canada without Quebec}| combine harvesting | Cut-off, U",
                    ),
                    {
                        "name": "Combine harvesting {Canada without Quebec}| combine harvesting | Cut-off, S - Copied from Ecoinvent U"
                    },
                ),
                (
                    (
                        "Fertilising, by broadcaster {Canada without Quebec}| fertilising, by broadcaster | Cut-off, U",
                    ),
                    {
                        "name": "Fertilising, by broadcaster {Canada without Quebec}| fertilising, by broadcaster | Cut-off, S - Copied from Ecoinvent U"
                    },
                ),
                (
                    (
                        "Land use change, annual crop {CA}| market for land use change, annual crop | Cut-off, U",
                    ),
                    {
                        "name": "Land use change, annual crop {CA}| market for land use change, annual crop | Cut-off, S - Copied from Ecoinvent U"
                    },
                ),
                (
                    ("Peat moss {GLO}| market for peat moss | Cut-off, U",),
                    {
                        "name": "Peat moss {GLO}| market for | Cut-off, S - Copied from Ecoinvent U"
                    },
                ),
                (
                    ("Sowing {Canada without Quebec}| sowing | Cut-off, U",),
                    {
                        "name": "Sowing {Canada without Quebec}| sowing | Cut-off, S - Copied from Ecoinvent U"
                    },
                ),
                (
                    (
                        "Swath, by rotary windrower {Canada without Quebec}| swath, by rotary windrower | Cut-off, U",
                    ),
                    {
                        "name": "Swath, by rotary windrower {Canada without Quebec}| swath, by rotary windrower | Cut-off, S - Copied from Ecoinvent U"
                    },
                ),
                (
                    (
                        "Tillage, cultivating, chiselling {Canada without Quebec}| tillage, cultivating, chiselling | Cut-off, U",
                    ),
                    {
                        "name": "Tillage, cultivating, chiselling {Canada without Quebec}| tillage, cultivating, chiselling | Cut-off, S - Copied from Ecoinvent U"
                    },
                ),
                (
                    (
                        "Tillage, harrowing, by offset disc harrow {CA}| tillage, harrowing, by offset disc harrow | Cut-off, U",
                    ),
                    {
                        "name": "Tillage, harrowing, by offset disc harrow {CA}| tillage, harrowing, by offset disc harrow | Cut-off, S - Copied from Ecoinvent U"
                    },
                ),
                (
                    (
                        "Tillage, harrowing, by rotary harrow {CA}| tillage, harrowing, by rotary harrow | Cut-off, U",
                    ),
                    {
                        "name": "Tillage, harrowing, by rotary harrow {CA}| tillage, harrowing, by rotary harrow | Cut-off, S - Copied from Ecoinvent U"
                    },
                ),
                (
                    (
                        "Tillage, rolling {Canada without Quebec}| tillage, rolling | Cut-off, U",
                    ),
                    {
                        "name": "Tillage, rolling {Canada without Quebec}| tillage, rolling | Cut-off, S - Copied from Ecoinvent U"
                    },
                ),
                (
                    (
                        "Tillage, rotary cultivator {Canada without Quebec}| tillage, rotary cultivator | Cut-off, U",
                    ),
                    {
                        "name": "Tillage, rotary cultivator {Canada without Quebec}| tillage, rotary cultivator | Cut-off, S - Copied from Ecoinvent U"
                    },
                ),
                (
                    (
                        "Application of plant protection product, by field sprayer {Canada without Quebec}| application of plant protection product, by field sprayer | Cut-off, U",
                    ),
                    {
                        "name": "Application of plant protection product, by field sprayer {Canada without Quebec}| application of plant protection product, by field sprayer | Cut-off, S - Copied from Ecoinvent U"
                    },
                ),
                (
                    ("Zinc {GLO}| market for zinc | Cut-off, U",),
                    {
                        "name": "Zinc {GLO}| market for | Cut-off, S - Copied from Ecoinvent U"
                    },
                ),
                (
                    (
                        "Transport, freight train {GLO}| market group for transport, freight train | Cut-off, U",
                    ),
                    {
                        "name": "Transport, freight train {GLO}| market group for | Cut-off, S - Copied from Ecoinvent U"
                    },
                ),
                (
                    (
                        "Transport, freight, inland waterways, barge {GLO}| market group for transport, freight, inland waterways, barge | Cut-off, U",
                    ),
                    {
                        "name": "Transport, freight, inland waterways, barge {GLO}| market group for transport, freight, inland waterways, barge | Cut-off, S - Copied from Ecoinvent U"
                    },
                ),
                (
                    (
                        "Transport, freight, lorry, unspecified {GLO}| market group for transport, freight, lorry, unspecified | Cut-off, U",
                    ),
                    {
                        "name": "Transport, freight, lorry, unspecified {GLO}| market group for transport, freight, lorry, unspecified | Cut-off, S - Copied from Ecoinvent U"
                    },
                ),
                (
                    (
                        "Transport, freight, sea, bulk carrier for dry goods {GLO}| market for transport, freight, sea, bulk carrier for dry goods | Cut-off, U",
                    ),
                    {
                        "name": "Transport, freight, sea, bulk carrier for dry goods {GLO}| market for transport, freight, sea, bulk carrier for dry goods | Cut-off, S - Copied from Ecoinvent U"
                    },
                ),
            ],
        },
    }
]
# migrations necessary to link some remaining unlinked technosphere activities
AGRIBALYSE_MIGRATIONS = [
    {
        "name": "agb-technosphere-fixes",
        "description": "Specific technosphere fixes for Agribalyse 3",
        "data": {
            "fields": ["name", "unit"],
            "data": [
                (
                    (
                        "Wastewater, average {Europe without Switzerland}| market for wastewater, average | Cut-off, S - Copied from Ecoinvent U",
                        "l",
                    ),
                    {"unit": "m3", "multiplier": 1e-3},
                ),
                (
                    (
                        "Wastewater, from residence {RoW}| market for wastewater, from residence | Cut-off, S - Copied from Ecoinvent U",
                        "l",
                    ),
                    {"unit": "m3", "multiplier": 1e-3},
                ),
                (
                    (
                        "Heat, central or small-scale, natural gas {Europe without Switzerland}| market for heat, central or small-scale, natural gas | Cut-off, S - Copied from Ecoinvent U",
                        "kWh",
                    ),
                    {"unit": "MJ", "multiplier": 3.6},
                ),
                (
                    (
                        "Heat, district or industrial, natural gas {Europe without Switzerland}| heat production, natural gas, at industrial furnace >100kW | Cut-off, S - Copied from Ecoinvent U",
                        "kWh",
                    ),
                    {"unit": "MJ", "multiplier": 3.6},
                ),
                (
                    (
                        "Heat, district or industrial, natural gas {RER}| market group for | Cut-off, S - Copied from Ecoinvent U",
                        "kWh",
                    ),
                    {"unit": "MJ", "multiplier": 3.6},
                ),
                (
                    (
                        "Heat, district or industrial, natural gas {RoW}| market for heat, district or industrial, natural gas | Cut-off, S - Copied from Ecoinvent U",
                        "kWh",
                    ),
                    {"unit": "MJ", "multiplier": 3.6},
                ),
                (
                    (
                        "Land use change, perennial crop {BR}| market group for land use change, perennial crop | Cut-off, S - Copied from Ecoinvent U",
                        "m2",
                    ),
                    {"unit": "ha", "multiplier": 1e-4},
                ),
            ]
            + sum(
                [
                    [
                        [
                            (f"Water, river, {country}", "l"),
                            {"unit": "cubic meter", "multiplier": 0.001},
                        ],
                        [
                            (f"Water, well, {country}", "l"),
                            {"unit": "cubic meter", "multiplier": 0.001},
                        ],
                    ]
                    # only ES for AGB, all for Ginko
                    for country in ["ES", "ID", "CO", "CR", "EC", "IN", "BR", "US"]
                ],
                [],
            ),
        },
    }
]

PASTOECO_MIGRATIONS = [
    {
        "name": "pastoeco-technosphere-fixes",
        "description": "Fixes to ease linking to agb",
        "data": {
            "fields": ("name",),
            "data": [
                (
                    ("Diesel {Europe without Switzerland}| market for | Cut-off, S",),
                    {
                        "name": "Diesel {Europe without Switzerland}| market for | Cut-off, S - Copied from Ecoinvent U"
                    },
                ),
                (
                    ("Petrol, two-stroke blend {GLO}| market for | Cut-off, S",),
                    {
                        "name": "Petrol, two-stroke blend {GLO}| market for | Cut-off, S - Copied from Ecoinvent U"
                    },
                ),
                (
                    (
                        "Tap water {Europe without Switzerland}| market for | Cut-off, S",
                    ),
                    {
                        "name": "Tap water {Europe without Switzerland}| market for | Cut-off, S - Copied from Ecoinvent U"
                    },
                ),
                (
                    ("Electricity, low voltage {FR}| market for | Cut-off, S",),
                    {
                        "name": "Electricity, low voltage {FR}| market for | Cut-off, S - Copied from Ecoinvent U"
                    },
                ),
                (
                    (
                        "Newborn dairy calf, Conventional, Alsace, at farm gate, FR - MEANS#16615 U",
                    ),
                    {
                        "name": "Newborn dairy calf, Conventional, Alsace, at farm gate - MEANS#16615, FR"
                    },
                ),
            ],
        },
    }
]


def remove_azadirachtine(db):
    """Remove all exchanges with azadirachtine, except for apples"""
    new_db = []
    for ds in db:
        new_ds = copy.deepcopy(ds)
        new_ds["exchanges"] = [
            exc
            for exc in ds["exchanges"]
            if (
                "azadirachtin" not in exc.get("name", "").lower()
                or ds.get("name", "").lower().startswith("apple")
            )
        ]
        new_db.append(new_ds)
    return new_db


def remove_negative_land_use_on_tomato(db):
    """Remove transformation flows from urban on greenhouses
    that cause negative land-use on tomatoes"""
    new_db = []
    for ds in db:
        new_ds = copy.deepcopy(ds)
        if ds.get("name", "").lower().startswith("plastic tunnel"):
            new_ds["exchanges"] = [
                exc
                for exc in ds["exchanges"]
                if not exc.get("name", "")
                .lower()
                .startswith("transformation, from urban")
            ]
        else:
            pass
        new_db.append(new_ds)
    return new_db


def fix_lentil_ldu(db):
    """Replace 'from unspecified' with 'from annual crop'
    to avoid having negative LDU on the lentils.
    Should be removed for AGB 3.2"""
    new_db = []
    for ds in db:
        new_ds = copy.deepcopy(ds)
        if ds.get("name", "").startswith("Lentil"):
            for exc in new_ds["exchanges"]:
                if exc.get("name", "").startswith("Transformation, from unspecified"):
                    exc["name"] = "Transformation, from annual crop"
        else:
            pass
        new_db.append(new_ds)
    return new_db


def remove_some_processes(db):
    """Some processes make the whole import fail
    due to inability to parse the Input and Calculated parameters"""
    new_db = []
    for ds in db:
        new_ds = copy.deepcopy(ds)
        if ds.get("simapro metadata", {}).get("Process identifier") not in (
            "EI3CQUNI000025017103662",
        ):
            new_db.append(new_ds)
    return new_db


GINKO_STRATEGIES = [
    remove_negative_land_use_on_tomato,
    remove_azadirachtine,
    fix_lentil_ldu,
    functools.partial(
        link_technosphere_by_activity_hash_ref_product,
        external_db_name="Agribalyse 3.1.1",
        fields=("name", "unit"),
    ),
]
AGB_STRATEGIES = [remove_negative_land_use_on_tomato]

if __name__ == "__main__":
    """Import Agribalyse and additional processes"""
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--recreate-activities",
        action="store_true",
        help="Delete and re-create the created activities",
    )
    args = parser.parse_args()

    setup_project()

    # AGRIBALYSE 3.1.1
    if (db := "Agribalyse 3.1.1") not in bw2data.databases:
        import_simapro_csv(
            join(DB_FILES_DIR, AGRIBALYSE31),
            db,
            migrations=AGRIBALYSE_MIGRATIONS,
            strategies=STRATEGIES + AGB_STRATEGIES,
        )
    else:
        print(f"{db} already imported")

    # PASTO ECO
    if (db := "PastoEco") not in bw2data.databases:
        import_simapro_csv(
            join(DB_FILES_DIR, PASTOECO),
            db,
            external_db="Agribalyse 3.1.1",
            migrations=PASTOECO_MIGRATIONS,
            strategies=STRATEGIES,
        )
    else:
        print(f"{db} already imported")

    # GINKO
    if (db := "Ginko") not in bw2data.databases:
        import_simapro_csv(
            join(DB_FILES_DIR, GINKO),
            db,
            strategies=STRATEGIES + GINKO_STRATEGIES,
            migrations=GINKO_MIGRATIONS + AGRIBALYSE_MIGRATIONS,
        )
    else:
        print(f"{db} already imported")

    # CTCPA
    if (db := "CTCPA") not in bw2data.databases:
        import_simapro_csv(join(DB_FILES_DIR, CTCPA), db, strategies=STRATEGIES)
    else:
        print(f"{db} already imported")

    # WFLDB
    if (db := "WFLDB") not in bw2data.databases:
        import_simapro_csv(join(DB_FILES_DIR, WFLDB), db, strategies=STRATEGIES)
    else:
        print(f"{db} already imported")

    if args.recreate_activities:
        if "Ecobalyse" in bw2data.databases:
            del bw2data.databases["Ecobalyse"]
