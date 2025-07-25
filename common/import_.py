import functools
import json
import os
import re
import sys
import tempfile
from enum import StrEnum
from os.path import basename, join, splitext
from pathlib import Path
from typing import List, Optional
from zipfile import ZipFile

import bw2data
import bw2io
from bw2io.strategies.generic import link_iterable_by_fields
from bw2io.utils import activity_hash
from tqdm import tqdm

from common import biosphere, patch_agb3
from common.bw.simapro_json import SimaProJsonImporter
from config import settings
from ecobalyse_data.bw.search import search_one
from ecobalyse_data.logging import logger


class ActivityFrom(StrEnum):
    SCRATCH = "from_scratch"
    EXISTING = "from_existing"


class ExchangeType(StrEnum):
    TECHNOSPHERE = "technosphere"
    BIOSPHERE = "biosphere"


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


def setup_project(
    project_name=settings.bw.project,
    biosphere_name=settings.bw.biosphere,
    db_files_dir=DB_FILES_DIR,
    biosphere_flows=settings.files.biosphere_flows,
    biosphere_lcia=settings.files.biosphere_lcia,
    setup_biosphere=True,
):
    bw2data.projects.set_current(project_name)

    if setup_biosphere:
        bw2data.preferences["biosphere_database"] = biosphere_name

        if biosphere_name in bw2data.databases:
            print(
                f"-> Biosphere database {biosphere_name} already present, no setup is needed, skipping."
            )
            return

        biosphere.create_ecospold_biosphere(
            dbname=biosphere_name,
            filepath=os.path.join(db_files_dir, biosphere_flows),
        )

        biosphere.create_biosphere_lcia_methods(
            filepath=os.path.join(db_files_dir, biosphere_lcia),
        )

    add_missing_substances(project_name, biosphere_name)

    bw2io.create_core_migrations()


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


def search_activity(activity: str, default_db: str | None = None):
    return search_one(*get_db_and_activity_name(activity, default_db))


def get_db_and_activity_name(
    full_activity_name: str, default_db: str | None = None
) -> tuple[str, str]:
    """
    Get the database and activity name from a full activity name.
    If the activity contains "::", then the first element is the database name and the second is the activity name.
    Otherwise, the db is default_db.
    """
    if "::" in full_activity_name:
        if full_activity_name.count("::") > 1:
            raise ValueError("Activity name should contain only one '::'")
        db_name, activity_name = full_activity_name.split("::")
        return db_name, activity_name
    elif default_db is not None:
        return default_db, full_activity_name
    else:
        raise ValueError(
            "No database specified. Provide default_db or use 'database::name' format for activity"
        )


def create_activity(dbname, new_activity_name, base_activity=None):
    """Creates a new activity by copying a base activity or from nothing. Returns the created activity"""
    if "constructed by Ecobalyse" not in new_activity_name:
        new_activity_name = f"{new_activity_name}, constructed by Ecobalyse"
    else:
        new_activity_name = f"{new_activity_name}"

    if base_activity:
        data = base_activity.as_dict().copy()
        del data["code"]
        # Id should be autogenerated or BW will throw an error
        # `id` must be created automatically, but `id=137934742532190208` given
        if "id" in data:
            del data["id"]
        data["name"] = new_activity_name
        data["System description"] = "Ecobalyse"
        data["database"] = "Ecobalyse"
        # see https://github.com/brightway-lca/brightway2-data/blob/main/CHANGES.md#40dev57-2024-10-03
        data["type"] = "processwithreferenceproduct"
        code = activity_hash(data)
        new_activity = base_activity.copy(code, **data)
    else:
        data = {
            "production amount": 1,
            "unit": "kilogram",
            # see https://github.com/brightway-lca/brightway2-data/blob/main/CHANGES.md#40dev57-2024-10-03
            "type": "processwithreferenceproduct",
            "comment": "added by Ecobalyse",
            "name": new_activity_name,
            "System description": "Ecobalyse",
        }
        code = activity_hash(data)
        new_activity = bw2data.Database(dbname).new_activity(code, **data)
        new_activity["code"] = code
    new_activity["Process identifier"] = code
    new_activity.save()
    logger.info(f"Created activity {new_activity}")
    return new_activity


def add_created_activities(created_activities_db, activities_to_create):
    """
    Once the agribalyse database has been imported, add to the database the new activities defined in `ACTIVITIES_TO_CREATE.json`.
    """
    with open(activities_to_create, "r") as f:
        activities_data = json.load(f)

    bw2data.Database(created_activities_db).register()

    for activity_data in activities_data:
        logger.info(
            f"-> Creating activity {activity_data.get('activityCreationType')} '{activity_data.get('alias')}'"
        )
        if activity_data.get("activityCreationType") == ActivityFrom.SCRATCH:
            add_activity_from_scratch(activity_data, created_activities_db)
        if activity_data.get("activityCreationType") == ActivityFrom.EXISTING:
            add_activity_from_existing(activity_data, created_activities_db)


def add_activity_from_scratch(activity_data, dbname):
    """Add to the database dbname a new activity created from scratch

    Example : the diesel, B7 activity is created from scratch with the following exchanges:
    - diesel, low-sulfur//[RER] market group for diesel, low-sulfur
    - fatty acid methyl ester//[RoW] market for fatty acid methyl ester
    - biosphere3::Carbon dioxide, fossil 349b29d1-3e58-4c66-98b9-9d1a076efd2e
    - biosphere3::Carbon monoxide, fossil, air, urban air close to ground 6edcc2df-88a3-48e1-83d8-ffc38d31c35b
    - biosphere3::NMVOC, non-methane volatile organic compounds, air, urban air close to ground 175baa64-d985-4c5e-84ef-67cc3a1cf952
    - biosphere3::Nitrogen oxides, air, urban air close to ground d068f3e2-b033-417b-a359-ca4f25da9731
    - biosphere3::Particulate Matter, < 2.5 um, air, urban air close to ground 230d8a0a-517c-43fe-8357-1818dd12997a
    the biosphere3 activities are outputs, because the type of the linked activities is "emission"
    """
    activity_from_scratch = create_activity(dbname, f"{activity_data['newName']}")
    for activity_name, amount in activity_data["exchanges"].items():
        activity_add = search_activity(activity_name, activity_data["database"])
        new_exchange(activity_from_scratch, activity_add, amount)

    activity_from_scratch.save()


def delete_exchange(activity, activity_to_delete, amount=False):
    """Deletes an exchange from an activity."""
    if amount:
        for exchange in activity.exchanges():
            if (
                exchange.input["name"] == activity_to_delete["name"]
                and exchange["amount"] == amount
            ):
                exchange.delete()
                logger.info(f"Deleted {exchange}")
                return

    else:
        for exchange in activity.exchanges():
            if exchange.input["name"] == activity_to_delete["name"]:
                exchange.delete()
                logger.info(f"Deleted {exchange}")
                return
    raise ValueError(f"Did not find exchange {activity_to_delete}. No exchange deleted")


def get_exchange_type(activity: dict) -> ExchangeType:
    """Get the type of an exchange based on the activity"""
    if activity.get("database") == "biosphere3":
        return ExchangeType.BIOSPHERE
    return ExchangeType.TECHNOSPHERE


def new_exchange(activity, new_activity, new_amount=None, activity_to_copy_from=None):
    """Create a new exchange. If an activity_to_copy_from is provided, the amount is copied from this activity. Otherwise, the amount is new_amount.

    activity: the activity to which the new exchange is added
    new_activity: the new exchange will link to this new_activity
    new_amount: the amount of the new exchange
    activity_to_copy_from: the activity from which the amount is copied
    """
    assert new_amount is not None or activity_to_copy_from is not None, (
        "No amount or activity to copy from provided"
    )
    if new_amount is None and activity_to_copy_from is not None:
        for exchange in list(activity.exchanges()):
            if exchange.input["name"] == activity_to_copy_from["name"]:
                new_amount = exchange["amount"]
                break
        else:
            raise ValueError(
                f"Exchange to duplicate from :{activity_to_copy_from} not found. No exchange added"
            )
            return

    new_exchange = activity.new_exchange(
        name=new_activity["name"],
        input=new_activity,
        amount=new_amount,
        type=get_exchange_type(new_activity),
        unit=new_activity["unit"],
        comment="added by Ecobalyse",
    )
    new_exchange.save()
    logger.info(f"Exchange {new_activity} added with amount: {new_amount}")


def replace_activities(new_activity, activity_data, base_db):
    """Replace all activities in activity_data["replace"] with variants of these activities"""
    for to_be_replaced, replacing in activity_data["replacementPlan"][
        "replace"
    ].items():
        activity_to_be_replaced = search_activity(to_be_replaced, base_db)
        activity_replacing = search_activity(replacing, base_db)
        new_exchange(
            new_activity,
            activity_replacing,
            activity_to_copy_from=activity_to_be_replaced,
        )
        delete_exchange(new_activity, activity_to_be_replaced)


def add_activity_from_existing(activity_data, created_activities_db):
    """Add to the database a new activity : the variant of an activity

    Example : ingredient flour-organic is not in agribalyse so it is created at this step. It's a
    variant of activity flour
    """
    default_db = activity_data["database"]
    # Example : the flour-conventional
    existing_activity = search_one(default_db, activity_data["existingActivity"])

    # create a new  activity
    # Example: this is where we create the flour-organic activity
    new_activity = create_activity(
        created_activities_db,
        f"{activity_data['newName']}",
        existing_activity,
    )

    if "delete" in activity_data:
        for upstream_activity_name in activity_data["delete"]:
            activity_to_delete = search_activity(
                upstream_activity_name, activity_data["database"]
            )
            delete_exchange(new_activity, activity_to_delete)

    if "replacementPlan" in activity_data:
        # if the activity has no upstream path, we can directly replace the seed activity with the seed
        #  activity variant
        if not activity_data["replacementPlan"]["upstreamPath"]:
            replace_activities(new_activity, activity_data, activity_data["database"])

        # else we have to iterate through the upstream path and create a new variant activity for each upstream activity

        # Example: for flour-organic we have to dig through the upstream process `global milling process` and
        #  replace the wheat activity with the wheat-organic activity
        else:
            for i, upstream_activity_data in enumerate(
                activity_data["replacementPlan"]["upstreamPath"]
            ):
                upstream_activity_db, upstream_activity_name = get_db_and_activity_name(
                    upstream_activity_data, default_db
                )

                upstream_activity = search_one(
                    upstream_activity_db,
                    upstream_activity_name,
                    excluded_term="declassified",
                )

                # create a new upstream_activity_variant
                upstream_activity_variant = create_activity(
                    created_activities_db,
                    f"{upstream_activity['name']} {activity_data['alias']}, constructed by Ecobalyse",
                    upstream_activity,
                )
                upstream_activity_variant.save()

                # link the newly created upstream_activity_variant to the parent activity_variant
                new_exchange(
                    new_activity,
                    upstream_activity_variant,
                    activity_to_copy_from=upstream_activity,
                )
                delete_exchange(new_activity, upstream_activity)

                # for the last sub activity, replace the seed activity with the seed activity variant
                # Example: for flour-organic this is where the replace the wheat activity with the
                # wheat-organic activity
                if i == len(activity_data["replacementPlan"]["upstreamPath"]) - 1:
                    replace_activities(
                        upstream_activity_variant, activity_data, upstream_activity_db
                    )

                # update the activity_variant (parent activity)
                new_activity = upstream_activity_variant


def add_unlinked_flows_to_biosphere_database(
    database,
    biosphere_name=None,
    fields={"name", "unit", "categories"},
) -> None:
    biosphere_name = biosphere_name or bw2data.config.biosphere
    assert biosphere_name in bw2data.databases, (
        "{} biosphere database not found".format(biosphere_name)
    )

    bio = bw2data.Database(biosphere_name)

    def reformat(exc):
        dct = {key: value for key, value in list(exc.items()) if key in fields}
        dct.update(
            type="emission",
            exchanges=[],
            code=activity_hash(dct),
            database=biosphere_name,
        )
        return dct

    new_data = [
        reformat(exc)
        for ds in database.data
        for exc in ds.get("exchanges", [])
        if exc["type"] == "biosphere" and not exc.get("input")
    ]

    # Dictionary eliminate duplicates
    # first load the new data with activity_hash
    data = {(biosphere_name, exc["code"]): exc for exc in new_data}
    # then deduplicate/overwrite them with original data
    # still using the activity_hash as a key but the uuis as internal code
    data.update(
        {(biosphere_name, activity_hash(exc)): exc for exc in bio.load().values()}
    )
    # then reconstruct data with the uuid
    data = {(biosphere_name, exc["code"]): exc for exc in data.values()}
    bio.write(data)

    database.apply_strategy(
        functools.partial(
            link_iterable_by_fields,
            other=(obj for obj in bw2data.Database(biosphere_name)),
            edge_kinds=["biosphere"],
        ),
    )


def import_simapro_csv(
    datapath,
    dbname,
    external_db=None,
    biosphere="biosphere3",
    migrations=[],
    strategies=[],
):
    """
    Import file at path `datapath` into database named `dbname`, and apply provided brightway `migrations`.
    """
    print(f"### Importing {datapath}...")

    # unzip
    with tempfile.TemporaryDirectory() as tempdir:
        json_datapath = Path(
            os.path.join(os.path.dirname(datapath), f"{Path(datapath).stem}.json")
        )
        json_datapath_zip = Path(f"{json_datapath}.zip")

        # Check if a json version exists
        if json_datapath.is_file() or json_datapath_zip.is_file():
            if not json_datapath.is_file() and json_datapath_zip.is_file():
                with ZipFile(json_datapath_zip) as zf:
                    print(f"### Extracting JSON the zip file in {tempdir}...")
                    zf.extractall(path=tempdir)
                    unzipped, _ = splitext(join(tempdir, basename(json_datapath_zip)))
                    json_datapath = Path(unzipped)

            print(f"### Importing into {dbname} from JSON...")
            database = SimaProJsonImporter(
                str(json_datapath), dbname, normalize_biosphere=True
            )

        else:
            with ZipFile(datapath) as zf:
                print(f"### Extracting the zip file in {tempdir}...")
                zf.extractall(path=tempdir)
                unzipped, _ = splitext(join(tempdir, basename(datapath)))

            if "AGB3" in datapath:
                patch_agb3(unzipped)

            print(
                f"### Importing into {dbname} from CSV (you should consider using the JSON importer)..."
            )
            database = bw2io.importers.simapro_csv.SimaProCSVImporter(unzipped, dbname)

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

    print("### Applying strategies...")
    database.strategies = strategies

    database.apply_strategies()
    database.statistics()

    # try to link remaining unlinked technosphere activities
    database.apply_strategy(
        functools.partial(
            link_technosphere_by_activity_hash_ref_product,
            fields=("name", "unit", "location"),
        )
    )
    database.apply_strategy(
        functools.partial(
            link_technosphere_by_activity_hash_ref_product, fields=("name", "unit")
        )
    )
    database.apply_strategy(
        functools.partial(
            link_technosphere_by_activity_hash_ref_product,
            external_db_name=external_db,
            fields=("name", "unit", "location"),
        )
    )
    database.apply_strategy(
        functools.partial(
            link_technosphere_by_activity_hash_ref_product,
            external_db_name=external_db,
            fields=("name", "unit"),
        )
    )
    database.apply_strategy(
        functools.partial(
            link_iterable_by_fields,
            other=bw2data.Database(biosphere),
            kind="biosphere",
        ),
    )

    database.statistics()

    print("### Adding unlinked flows and activities...")
    # comment to enable stopping on unlinked activities and creating an excel file
    add_unlinked_flows_to_biosphere_database(database, biosphere)
    database.add_unlinked_activities()

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
