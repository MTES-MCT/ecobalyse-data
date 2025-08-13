#!/usr/bin/env python3

import argparse
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
from ecobalyse_data.bw.migration import (
    AGRIBALYSE_MIGRATIONS,
    GINKO_MIGRATIONS,
    PASTOECO_MIGRATIONS,
)
from ecobalyse_data.bw.strategy import (
    fix_lentil_ldu,
    remove_acetamiprid,
    remove_azadirachtine,
    remove_creosote,
    remove_creosote_flows,
    remove_negative_land_use_on_tomato,
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


GINKO_STRATEGIES = [
    remove_negative_land_use_on_tomato,
    remove_azadirachtine,
    remove_creosote_flows,
    remove_acetamiprid,
    remove_creosote,
    fix_lentil_ldu,
    functools.partial(
        link_technosphere_by_activity_hash_ref_product,
        external_db_name="Agribalyse 3.1.1",
        fields=("name", "unit"),
    ),
]
AGB_STRATEGIES = [
    remove_negative_land_use_on_tomato,
    remove_creosote,
    remove_creosote_flows,
    remove_acetamiprid,
]
WFLDB_STRATEGIES = [remove_creosote_flows, remove_creosote, remove_acetamiprid]

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
        import_simapro_csv(
            join(DB_FILES_DIR, WFLDB), db, strategies=STRATEGIES + WFLDB_STRATEGIES
        )
    else:
        print(f"{db} already imported")

    if args.recreate_activities:
        if "Ecobalyse" in bw2data.databases:
            del bw2data.databases["Ecobalyse"]
