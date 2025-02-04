import functools
import json
import os
import re
import sys
from pathlib import Path
from typing import List, Optional
from subprocess import call
from timeit import default_timer as timer
import orjson


import bw2data
import bw2io

from bw2io.compatibility import SIMAPRO_BIO_SUBCATEGORIES, SIMAPRO_BIOSPHERE
from bw2io.strategies import (
    change_electricity_unit_mj_to_kwh,
    drop_unspecified_subcategories,
    fix_localized_water_flows,
    link_iterable_by_fields,
    link_technosphere_based_on_name_unit_location,
    migrate_datasets,
    migrate_exchanges,
    normalize_biosphere_categories,
    normalize_biosphere_names,
    normalize_simapro_biosphere_names,
    normalize_units,
    set_code_by_activity_hash,
    set_metadata_using_single_functional_exchange,
    split_simapro_name_geo,
    strip_biosphere_exc_locations,
    update_ecoinvent_locations,
    create_products_as_new_nodes,
)
from tqdm import tqdm

from common import biosphere
from common.export import create_activity, delete_exchange, new_exchange, search
from config import settings

AGRIBALYSE_PACKAGINGS = [
    "PS",
    "LDPE",
    "PP",
    "Cardboard",
    "No packaging",
    "Already packed - PET",
    "Glass",
    "Steel",
    "PVC",
    "PET",
    "Paper",
    "HDPE",
    "Already packed - PP/PE",
    "Already packed - Aluminium",
    "Already packed - Steel",
    "Already packed - Glass",
    "Corrugated board and aluminium packaging",
    "Corrugated board and LDPE packaging",
    "Aluminium",
    "PP/PE",
    "Corrugated board and PP packaging",
]
AGRIBALYSE_STAGES = ["at consumer", "at packaging", "at supermarket", "at distribution"]
AGRIBALYSE_TRANSPORT_TYPES = [
    "Chilled",
    "Ambient (average)",
    "Ambient (long)",
    "Ambient (short)",
    "Frozen",
]
AGRIBALYSE_PREPARATION_MODES = [
    "Oven",
    "No preparation",
    "Microwave",
    "Boiling",
    "Chilled at consumer",
    "Pan frying",
    "Water cooker",
    "Deep frying",
]


CURRENT_FILE_DIR = os.path.dirname(os.path.realpath(__file__))

DB_FILES_DIR = os.getenv(
    "DB_FILES_DIR",
    os.path.join(CURRENT_FILE_DIR, "..", "..", "dbfiles"),
)


def setup_project():
    bw2data.projects.set_current(settings.bw.project)
    bw2data.preferences["biosphere_database"] = settings.bw.biosphere

    if settings.bw.biosphere in bw2data.databases:
        print(
            f"-> Biosphere database {settings.bw.biosphere} already present, no setup is needed, skipping."
        )
        return

    biosphere.create_ecospold_biosphere(
        dbname=settings.bw.biosphere,
        filepath=os.path.join(DB_FILES_DIR, settings.files.biosphere_flows),
    )
    biosphere.create_biosphere_lcia_methods(
        filepath=os.path.join(DB_FILES_DIR, settings.files.biosphere_lcia),
    )

    bw2io.create_core_migrations()

    add_missing_substances(settings.bw.project, settings.bw.biosphere)


def link_technosphere_by_activity_hash_ref_product(
    db, external_db_name: Optional[str] = None, fields: Optional[List[str]] = None
):
    """
    This is a custom version of `bw2io.strategies.generic.link_technosphere_by_activity_hash`

    It adds the check for "processwithreferenceproduct" that was added in https://github.com/brightway-lca/brightway2-data/blob/main/CHANGES.md#40dev57-2024-10-03
    and avoid breaking the linking as processes are now imported with the default type "processwithreferenceproduct"
    """

    TECHNOSPHERE_TYPES = {"technosphere", "substitution", "production"}
    if external_db_name is not None:
        other = (
            obj
            for obj in bw2data.Database(external_db_name)
            if obj.get("type", "process") == "process"
            or obj.get("type") == "processwithreferenceproduct"
        )
        internal = False
    else:
        other = None
        internal = True
    return link_iterable_by_fields(
        db, other, internal=internal, kind=TECHNOSPHERE_TYPES, fields=fields
    )


def add_created_activities(dbname, activities_to_create):
    """
    Once the agribalyse database has been imported, add to the database the new activities defined in `ACTIVITIES_TO_CREATE.json`.
    """
    with open(activities_to_create, "r") as f:
        activities_data = json.load(f)

    bw2data.Database(dbname).register()

    for activity_data in activities_data:
        if "add" in activity_data:
            add_average_activity(activity_data, dbname)
        if "replace" in activity_data:
            add_variant_activity(activity_data, dbname)


def add_average_activity(activity_data, dbname):
    """Add to the database dbname a new activity : the weighted average of multiple activities

    Example : the average activity milk "Cow milk, organic, system n°1, at farm gate/FR U" is the
    weighted average of the activities 'Cow milk, organic, system n°1, at farm gate/FR U' from
    system 1 to 5
    """
    average_activity = create_activity(
        dbname, f"{activity_data['search']} {activity_data['suffix']}"
    )
    for activity_add_name, amount in activity_data["add"].items():
        activity_add = search(activity_data["search_in"], f"{activity_add_name}")
        new_exchange(average_activity, activity_add, amount)
    average_activity.save()


def replace_activities(activity_variant, activity_data, dbname):
    """Replace all activities in activity_data["replace"] with variants of these activities"""
    for old, new in activity_data["replace"].items():
        if isinstance(new, list):
            searchdb, new = new
        else:
            searchdb = dbname
        activity_old = search(dbname, old)
        activity_new = search(searchdb, new)
        new_exchange(
            activity_variant,
            activity_new,
            activity_to_copy_from=activity_old,
        )
        delete_exchange(activity_variant, activity_old)


def add_variant_activity(activity_data, dbname):
    """Add to the database a new activity : the variant of an activity

    Example : ingredient flour-organic is not in agribalyse so it is created at this step. It's a
    variant of activity flour
    """
    activity = search(activity_data["search_in"], activity_data["search"])

    # create a new variant activity
    # Example: this is where we create the flour-organic activity
    activity_variant = create_activity(
        dbname,
        f"{activity['name']} {activity_data['suffix']}",
        activity,
    )

    # if the activity has no subactivities, we can directly replace the seed activity with the seed
    #  activity variant
    if not activity_data["subactivities"]:
        replace_activities(activity_variant, activity_data, activity_data["search_in"])

    # else we have to iterate through subactivities and create a new variant activity for each subactivity

    # Example: for flour-organic we have to dig through the `global milling process` subactivity before
    #  we can replace the wheat activity with the wheat-organic activity
    else:
        for i, act_sub_data in enumerate(activity_data["subactivities"]):
            searchdb = None  # WARNING : the last database specified in "subactivities" is used in the "replace"
            if isinstance(act_sub_data, list):
                searchdb, act_sub_data = act_sub_data
            else:
                searchdb, act_sub_data = (
                    searchdb or activity_data["search_in"],
                    act_sub_data,
                )
            sub_activity = search(searchdb, act_sub_data, "declassified")
            nb = len(bw2data.Database(dbname).search(f"{sub_activity['name']}"))

            # create a new sub activity variant
            sub_activity_variant = create_activity(
                dbname,
                f"{sub_activity['name']} {activity_data['suffix']} (variant {nb})",
                sub_activity,
            )
            sub_activity_variant.save()

            # link the newly created sub_activity_variant to the parent activity_variant
            new_exchange(
                activity_variant,
                sub_activity_variant,
                activity_to_copy_from=sub_activity,
            )
            delete_exchange(activity_variant, sub_activity)

            # for the last sub activity, replace the seed activity with the seed activity variant
            # Example: for flour-organic this is where the replace the wheat activity with the
            # wheat-organic activity
            if i == len(activity_data["subactivities"]) - 1:
                replace_activities(sub_activity_variant, activity_data, searchdb)

            # update the activity_variant (parent activity)
            activity_variant = sub_activity_variant


def normalize_simapro_biosphere_context_into_categories(db):
    """
    Normalize biosphere categories in a dataset to the ecoinvent standard.

    Processes datasets and their exchanges by normalizing biosphere
    categories and subcategories to match the ecoinvent standard. It uses predefined
    mappings for SimaPro and ecoinvent categories.

    Fix simapro block csv import, categories is now context
    """
    for ds in db:
        for exc in (
            exc for exc in ds.get("exchanges", []) if exc["type"] == "biosphere"
        ):
            cat = SIMAPRO_BIOSPHERE.get(exc["context"][0], exc["context"][0])
            if len(exc["context"]) > 1:
                subcat = SIMAPRO_BIO_SUBCATEGORIES.get(
                    exc["context"][1], exc["context"][1]
                )
                exc["categories"] = (cat, subcat)
            else:
                exc["categories"] = (cat,)
    return db


def assign_only_product_as_production_for_block_importer(db):
    """
    patch of `assign_only_product_as_production` to be compatible with the new CSV block importer
    Assign only product as reference product.

    For each dataset in ``db``, this function checks if there is only one production exchange and
    no reference product already assigned. If this is the case, the reference product is set to the
    name of the production exchange, and the following fields are replaced if not already specified:

    """
    for ds in db:
        if ds.get("reference product") and ds.get("name") == ds.get(
            "reference product"
        ):
            continue
        products = [x for x in ds.get("exchanges", []) if x.get("type") == "production"]
        if len(products) == 1:
            product = products[0]
            assert product["name"]
            ds["reference product"] = (
                product.get("reference product", []) or product["name"]
            )
            ds["production amount"] = product["amount"]
            ds["name"] = product["name"]
            ds["unit"] = ds.get("unit") or product.get("unit") or "Unknown"
    return db


def use_ecoinvent_strategies(database, biosphere):
    """Switch strategy selection to normalize data to ecoinvent flow lists"""
    database.strategies = [
        set_metadata_using_single_functional_exchange,
        drop_unspecified_subcategories,
        normalize_units,
        update_ecoinvent_locations,
        # assign_only_product_as_production_for_block_importer,
        split_simapro_name_geo,
        strip_biosphere_exc_locations,
        functools.partial(migrate_datasets, migration="default-units"),
        functools.partial(migrate_exchanges, migration="default-units"),
        # Don't override code that are already present as they may be referenced by
        # mf_allocated_process_code
        # functools.partial(set_code_by_activity_hash, overwrite=True),
        functools.partial(set_code_by_activity_hash),
        change_electricity_unit_mj_to_kwh,
        create_products_as_new_nodes,
        link_technosphere_based_on_name_unit_location,
        normalize_biosphere_categories,
        normalize_simapro_biosphere_context_into_categories,
        normalize_biosphere_names,
        normalize_simapro_biosphere_names,
        functools.partial(migrate_exchanges, migration="simapro-water"),
        fix_localized_water_flows,
        functools.partial(
            link_iterable_by_fields,
            other=bw2data.Database(biosphere),
            edge_kinds=["biosphere"],
        ),
    ]

    return database


def import_simapro_block_csv(
    datapath,
    dbname,
    external_db=None,
    biosphere="biosphere3",
    migrations=[],
    first_strategies=[],
    excluded_strategies=[],
    other_strategies=[],
    source=None,
):
    print(f"### Importing {datapath}...")

    if "AGB3" in datapath:
        print("### Patching Agribalyse...")
        # `yield` is used as a variable in some Simapro parameters. bw2parameters cannot handle it:
        # (sed is faster than Python)
        call("sed -i 's/yield/Yield_/g' " + datapath, shell=True)
        # Fix some errors in Agribalyse:
        call("sed -i 's/01\\/03\\/2005/1\\/3\\/5/g' " + datapath, shell=True)
        call("sed -i 's/\"0;001172\"/0,001172/' " + datapath, shell=True)

    print(f"### Importing into {dbname}...")
    # Do the import
    start = timer()
    database = bw2io.importers.simapro_block_csv.SimaProBlockCSVImporter(
        Path(datapath),
        dbname,
        shorten_names=False,
        separate_products=False,
        biosphere_database_name=biosphere,
    )
    end = timer()
    print(
        f"[import_simapro_block_csv] seconds: {end - start}, minutes: {(end-start) / 60}"
    )  # Time in seconds

    database.statistics()

    if source:
        for ds in database:
            ds["source"] = source

    with open(f"new_block_simapro_importer_after_import_{dbname}.json", "wb") as f:
        f.write(orjson.dumps(database.data, option=orjson.OPT_INDENT_2))

    database = use_ecoinvent_strategies(database, biosphere)

    print("### Applying migrations...")
    # Apply provided migrations
    for migration in migrations:
        print(f"### Applying custom migration: {migration['description']}")
        bw2io.Migration(migration["name"]).write(
            migration["data"],
            description=migration["description"],
        )
        database.migrate(migration["name"])
    database.statistics()

    with open(f"new_block_simapro_importer_after_migrations_{dbname}.json", "wb") as f:
        f.write(orjson.dumps(database.data, option=orjson.OPT_INDENT_2))

    print("### Applying strategies...")
    # exclude strategies/migrations
    database.strategies = (
        list(first_strategies)
        + [
            s
            for s in database.strategies
            if not any([e in repr(s) for e in excluded_strategies])
        ]
        + list(other_strategies)
    )

    database.apply_strategies()
    database.statistics()
    # try to link remaining unlinked technosphere activities
    database.apply_strategy(
        functools.partial(
            link_technosphere_by_activity_hash_ref_product,
            external_db_name=external_db,
            fields=("name", "unit"),
        )
    )
    database.apply_strategy(
        functools.partial(
            link_technosphere_by_activity_hash_ref_product, fields=("name", "location")
        )
    )
    database.statistics()

    with open(f"new_block_simapro_importer_before_unlinked_{dbname}.json", "wb") as f:
        f.write(orjson.dumps(database.data, option=orjson.OPT_INDENT_2))

    print("### Adding unlinked flows and activities...")
    # comment to enable stopping on unlinked activities and creating an excel file
    database.add_unlinked_flows_to_biosphere_database(biosphere)
    database.add_unlinked_activities()

    database.statistics()

    with open(f"new_block_simapro_importer_after_unlinked_{dbname}.json", "wb") as f:
        f.write(orjson.dumps(database.data, option=orjson.OPT_INDENT_2))

    # stop if there are unlinked activities
    if len(list(database.unlinked)):
        database.write_excel(only_unlinked=True)
        print(
            "Look at the above excel file, there are still unlinked activities. Consider improving the migrations"
        )
        sys.exit(1)
    database.statistics()

    dsdict = {ds["code"]: ds for ds in database.data}
    database.data = list(dsdict.values())

    dqr_pattern = r"The overall DQR of this product is: (?P<overall>[\d.]+) {P: (?P<P>[\d.]+), TiR: (?P<TiR>[\d.]+), GR: (?P<GR>[\d.]+), TeR: (?P<TeR>[\d.]+)}"
    ciqual_pattern = r"\[Ciqual code: (?P<ciqual>[\d_]+)\]"
    location_pattern = r"\{(?P<location>[\w ,\/\-\+]+)\}"
    location_pattern_2 = r"\/\ *(?P<location>[\w ,\/\-]+) U$"

    print("### Applying additional transformations...")
    for activity in tqdm(database):
        # Getting activities locations
        if "name" not in activity:
            print("skipping en empty activity")
            continue
        if activity.get("location") is None:
            match = re.search(pattern=location_pattern, string=activity["name"])
            if match is not None:
                activity["location"] = match["location"]
            else:
                match = re.search(pattern=location_pattern_2, string=activity["name"])
                if match is not None:
                    activity["location"] = match["location"]
                elif ("French production," in activity["name"]) or (
                    "French production mix," in activity["name"]
                ):
                    activity["location"] = "FR"
                elif "CA - adapted for maple syrup" in activity["name"]:
                    activity["location"] = "CA"
                elif ", IT" in activity["name"]:
                    activity["location"] = "IT"
                elif ", TR" in activity["name"]:
                    activity["location"] = "TR"
                elif "/GLO" in activity["name"]:
                    activity["location"] = "GLO"

        # Getting products CIQUAL code when relevant
        if "ciqual" in activity["name"].lower():
            match = re.search(pattern=ciqual_pattern, string=activity["name"])
            activity["ciqual_code"] = match["ciqual"] if match is not None else ""

        # Putting SimaPro metadata in the activity fields directly and removing references to SimaPro
        if "simapro metadata" in activity:
            for sp_field, value in activity["simapro metadata"].items():
                if value != "Unspecified":
                    activity[sp_field] = value

            # Getting the Data Quality Rating of the data when relevant
            if "Comment" in activity["simapro metadata"]:
                match = re.search(
                    pattern=dqr_pattern, string=activity["simapro metadata"]["Comment"]
                )

                if match:
                    activity["DQR"] = {
                        "overall": float(match["overall"]),
                        "P": float(match["P"]),
                        "TiR": float(match["TiR"]),
                        "GR": float(match["GR"]),
                        "TeR": float(match["TeR"]),
                    }

            del activity["simapro metadata"]

        # Getting activity tags
        name_without_spaces = activity["name"].replace(" ", "")
        for packaging in AGRIBALYSE_PACKAGINGS:
            if f"|{packaging.replace(' ', '')}|" in name_without_spaces:
                activity["packaging"] = packaging

        for stage in AGRIBALYSE_STAGES:
            if f"|{stage.replace(' ', '')}" in name_without_spaces:
                activity["stage"] = stage

        for transport_type in AGRIBALYSE_TRANSPORT_TYPES:
            if f"|{transport_type.replace(' ', '')}|" in name_without_spaces:
                activity["transport_type"] = transport_type

        for preparation_mode in AGRIBALYSE_PREPARATION_MODES:
            if f"|{preparation_mode.replace(' ', '')}|" in name_without_spaces:
                activity["preparation_mode"] = preparation_mode

        if "simapro name" in activity:
            del activity["simapro name"]

        if "filename" in activity:
            del activity["filename"]

    database.statistics()

    with open(f"new_block_simapro_importer_before_writing_{dbname}.json", "wb") as f:
        f.write(orjson.dumps(database.data, option=orjson.OPT_INDENT_2))

    bw2data.Database(biosphere).register()
    database.write_database()
    print(f"### Finished importing {datapath}\n")


def import_simapro_csv(
    datapath,
    dbname,
    external_db=None,
    biosphere="biosphere3",
    migrations=[],
    first_strategies=[],
    excluded_strategies=[],
    other_strategies=[],
    source=None,
):
    """
    Import file at path `datapath` into database named `dbname`, and apply provided brightway `migrations`.
    """
    print(f"### Importing {datapath}...")
    # unzip
    # with tempfile.TemporaryDirectory() as tempdir:
    #     with ZipFile(datapath) as zf:
    #         print(f"### Extracting the zip file in {tempdir}...")
    #         zf.extractall(path=tempdir)
    #         unzipped, _ = splitext(join(tempdir, basename(datapath)))
    #
    if "AGB3" in datapath:
        print("### Patching Agribalyse...")
        # `yield` is used as a variable in some Simapro parameters. bw2parameters cannot handle it:
        # (sed is faster than Python)
        call("sed -i 's/yield/Yield_/g' " + datapath, shell=True)
        # Fix some errors in Agribalyse:
        call("sed -i 's/01\\/03\\/2005/1\\/3\\/5/g' " + datapath, shell=True)
        call("sed -i 's/\"0;001172\"/0,001172/' " + datapath, shell=True)
    #
    print(f"### Importing into {dbname}...")
    # Do the import

    start = timer()
    database = bw2io.importers.simapro_csv.SimaProCSVImporter(
        datapath, dbname, normalize_biosphere=True
    )

    end = timer()
    print(
        f"[import_simapro_csv] seconds: {end - start}, minutes: {(end-start) / 60}"
    )  # Time in seconds

    database.statistics()

    if source:
        for ds in database:
            ds["source"] = source

    database.statistics()

    with open("legacy_simapro_importer_agb_after_import.json", "w") as fp:
        json.dump(database.data, fp, indent=2)

    print("### Applying migrations...")
    # Apply provided migrations
    for migration in migrations:
        print(f"### Applying custom migration: {migration['description']}")
        bw2io.Migration(migration["name"]).write(
            migration["data"],
            description=migration["description"],
        )
        database.migrate(migration["name"])
    database.statistics()

    with open("legacy_simapro_importer_agb_after_migrations.json", "w") as fp:
        json.dump(database.data, fp, indent=2)

    print("### Applying strategies...")
    # exclude strategies/migrations
    database.strategies = (
        list(first_strategies)
        + [
            s
            for s in database.strategies
            if not any([e in repr(s) for e in excluded_strategies])
        ]
        + list(other_strategies)
    )

    database.apply_strategies()
    database.statistics()
    # try to link remaining unlinked technosphere activities
    database.apply_strategy(
        functools.partial(
            link_technosphere_by_activity_hash_ref_product,
            external_db_name=external_db,
            fields=("name", "unit"),
        )
    )
    database.apply_strategy(
        functools.partial(
            link_technosphere_by_activity_hash_ref_product, fields=("name", "location")
        )
    )
    database.statistics()

    with open("legacy_simapro_importer_agb_before_unlinked.json", "w") as fp:
        json.dump(database.data, fp, indent=2)

    print("### Adding unlinked flows and activities...")
    # comment to enable stopping on unlinked activities and creating an excel file
    database.add_unlinked_flows_to_biosphere_database(biosphere)
    database.add_unlinked_activities()

    database.statistics()

    with open("legacy_simapro_importer_agb_after_unlinked.json", "w") as fp:
        json.dump(database.data, fp, indent=2)

    # stop if there are unlinked activities
    if len(list(database.unlinked)):
        database.write_excel(only_unlinked=True)
        print(
            "Look at the above excel file, there are still unlinked activities. Consider improving the migrations"
        )
        sys.exit(1)
    database.statistics()

    dsdict = {ds["code"]: ds for ds in database.data}
    database.data = list(dsdict.values())

    dqr_pattern = r"The overall DQR of this product is: (?P<overall>[\d.]+) {P: (?P<P>[\d.]+), TiR: (?P<TiR>[\d.]+), GR: (?P<GR>[\d.]+), TeR: (?P<TeR>[\d.]+)}"
    ciqual_pattern = r"\[Ciqual code: (?P<ciqual>[\d_]+)\]"
    location_pattern = r"\{(?P<location>[\w ,\/\-\+]+)\}"
    location_pattern_2 = r"\/\ *(?P<location>[\w ,\/\-]+) U$"

    print("### Applying additional transformations...")
    for activity in tqdm(database):
        # Getting activities locations
        if "name" not in activity:
            print("skipping en empty activity")
            continue
        if activity.get("location") is None:
            match = re.search(pattern=location_pattern, string=activity["name"])
            if match is not None:
                activity["location"] = match["location"]
            else:
                match = re.search(pattern=location_pattern_2, string=activity["name"])
                if match is not None:
                    activity["location"] = match["location"]
                elif ("French production," in activity["name"]) or (
                    "French production mix," in activity["name"]
                ):
                    activity["location"] = "FR"
                elif "CA - adapted for maple syrup" in activity["name"]:
                    activity["location"] = "CA"
                elif ", IT" in activity["name"]:
                    activity["location"] = "IT"
                elif ", TR" in activity["name"]:
                    activity["location"] = "TR"
                elif "/GLO" in activity["name"]:
                    activity["location"] = "GLO"

        # Getting products CIQUAL code when relevant
        if "ciqual" in activity["name"].lower():
            match = re.search(pattern=ciqual_pattern, string=activity["name"])
            activity["ciqual_code"] = match["ciqual"] if match is not None else ""

        # Putting SimaPro metadata in the activity fields directly and removing references to SimaPro
        if "simapro metadata" in activity:
            for sp_field, value in activity["simapro metadata"].items():
                if value != "Unspecified":
                    activity[sp_field] = value

            # Getting the Data Quality Rating of the data when relevant
            if "Comment" in activity["simapro metadata"]:
                match = re.search(
                    pattern=dqr_pattern, string=activity["simapro metadata"]["Comment"]
                )

                if match:
                    activity["DQR"] = {
                        "overall": float(match["overall"]),
                        "P": float(match["P"]),
                        "TiR": float(match["TiR"]),
                        "GR": float(match["GR"]),
                        "TeR": float(match["TeR"]),
                    }

            del activity["simapro metadata"]

        # Getting activity tags
        name_without_spaces = activity["name"].replace(" ", "")
        for packaging in AGRIBALYSE_PACKAGINGS:
            if f"|{packaging.replace(' ', '')}|" in name_without_spaces:
                activity["packaging"] = packaging

        for stage in AGRIBALYSE_STAGES:
            if f"|{stage.replace(' ', '')}" in name_without_spaces:
                activity["stage"] = stage

        for transport_type in AGRIBALYSE_TRANSPORT_TYPES:
            if f"|{transport_type.replace(' ', '')}|" in name_without_spaces:
                activity["transport_type"] = transport_type

        for preparation_mode in AGRIBALYSE_PREPARATION_MODES:
            if f"|{preparation_mode.replace(' ', '')}|" in name_without_spaces:
                activity["preparation_mode"] = preparation_mode

        if "simapro name" in activity:
            del activity["simapro name"]

        if "filename" in activity:
            del activity["filename"]

    database.statistics()
    bw2data.Database(biosphere).register()
    database.write_database()
    print(f"### Finished importing {datapath}\n")


def add_missing_substances(project, biosphere):
    """Two additional substances provided by ecoinvent and that seem to be in 3.9.2 but not in 3.9.1"""
    substances = {
        "a35f0a31-fe92-56db-b0ca-cc878d270fde": {
            "name": "Hydrogen cyanide",
            "synonyms": ["Hydrocyanic acid", "Formic anammonide", "Formonitrile"],
            "categories": ("air",),
            "unit": "kilogram",
            "CAS Number": "000074-90-8",
            "formula": "HCN",
        },
        "ea53a165-9f19-54f2-90a3-3e5c7a05051f": {
            "name": "N,N-Dimethylformamide",
            "synonyms": ["Formamide, N,N-dimethyl-", "Dimethyl formamide"],
            "categories": ("air",),
            "unit": "kilogram",
            "CAS Number": "000068-12-2",
            "formula": "C3H7NO",
        },
    }
    bw2data.projects.set_current(project)
    bio = bw2data.Database(biosphere)
    for code, activity in substances.items():
        if not [flow for flow in bio if flow["code"] == code]:
            bio.new_activity(code, **activity)
