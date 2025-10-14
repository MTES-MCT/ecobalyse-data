#!/usr/bin/env python3

# from bw2io.migrations import create_core_migrations
import functools
import os
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
from ecobalyse_data.bw.migration import WOOLMARK_MIGRATIONS
from ecobalyse_data.bw.strategy import (
    extract_ciqual,
    extract_name_location_product,
    # extract_simapro_location,
    extract_simapro_metadata,
    extract_tags,
    lower_formula_parameters,
    organic_cotton_irrigation,
    remove_acetamiprid,
    remove_creosote,
    use_unit_processes,
)

CURRENT_FILE_DIR = os.path.dirname(os.path.realpath(__file__))

# Ecoinvent
EI391 = "./Ecoinvent3.9.1.CSV.zip"
EI311 = "./Ecoinvent3.11.CSV.zip"
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
ECOINVENT_STRATEGIES = [
    extract_simapro_metadata,
    # extract_simapro_location,
    extract_ciqual,
    extract_name_location_product,
    extract_tags,
    organic_cotton_irrigation,
    remove_creosote,
    remove_acetamiprid,
]

WOOLMARK_STRATEGIES = [use_unit_processes]


def main():
    setup_project()

    if (db := "Ecoinvent 3.11") not in bw2data.databases:
        import_simapro_csv(
            join(DB_FILES_DIR, EI311),
            db,
            strategies=STRATEGIES + ECOINVENT_STRATEGIES,
        )
    else:
        print(f"{db} already imported")

    if (db := "Ecoinvent 3.9.1") not in bw2data.databases:
        import_simapro_csv(
            join(DB_FILES_DIR, EI391),
            db,
            strategies=STRATEGIES + ECOINVENT_STRATEGIES,
        )
    else:
        print(f"{db} already imported")

    if (db := "Woolmark") not in bw2data.databases:
        import_simapro_csv(
            join(DB_FILES_DIR, WOOL),
            db,
            migrations=WOOLMARK_MIGRATIONS,
            strategies=[lower_formula_parameters] + STRATEGIES + WOOLMARK_STRATEGIES,
            external_db="Ecoinvent 3.9.1",
        )
    else:
        print(f"{db} already imported")


if __name__ == "__main__":
    main()
