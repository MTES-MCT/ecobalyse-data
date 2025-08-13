#!/usr/bin/env python3
import functools
import os
from os.path import dirname, join
from zipfile import ZipFile

import bw2data
import bw2io
from bw2io.strategies import (
    # drop_unlinked_cfs,
    drop_unspecified_subcategories,
    link_iterable_by_fields,
    match_subcategories,
    normalize_biosphere_categories,
    normalize_biosphere_names,
    normalize_simapro_biosphere_categories,
    normalize_simapro_biosphere_names,
    normalize_units,
    set_biosphere_type,
)
from frozendict import frozendict

from common import brightway_patch as brightway_patch
from common.import_ import DB_FILES_DIR, setup_project
from config import settings
from ecobalyse_data.bw.strategy import noLT, uraniumFRU

CURRENT_FILE_DIR = os.path.dirname(os.path.realpath(__file__))
METHODNAME = "Environmental Footprint 3.1 (adapted) patch wtu"  # defined inside the csv
METHODPATH = join(DB_FILES_DIR, METHODNAME + ".CSV.zip")


def import_method(datapath=METHODPATH, biosphere=settings.bw.biosphere):
    """
    Import file at path `datapath` linked to biosphere named `dbname`
    """
    print(f"biosphere3 size: {len(bw2data.Database('biosphere3'))}")
    print(f"### Importing {datapath}...")

    # unzip
    with ZipFile(datapath) as zf:
        print("### Extracting the zip file...")
        zf.extractall(path=dirname(datapath))
        unzipped = datapath[0:-4]

    print(f"biosphere3 size: {len(bw2data.Database('biosphere3'))}")
    ef = bw2io.importers.SimaProLCIACSVImporter(unzipped, biosphere=biosphere)

    os.unlink(unzipped)
    ef.statistics()

    ef.strategies = [
        normalize_units,
        set_biosphere_type,
        drop_unspecified_subcategories,
        functools.partial(normalize_biosphere_categories, lcia=True),
        functools.partial(normalize_biosphere_names, lcia=True),
        normalize_simapro_biosphere_categories,
        normalize_simapro_biosphere_names,
        functools.partial(
            link_iterable_by_fields,
            other=(
                obj
                for obj in bw2data.Database(ef.biosphere_name)
                if obj.get("type") == "emission"
            ),
            kind="biosphere",
        ),
        functools.partial(match_subcategories, biosphere_db_name=ef.biosphere_name),
    ]
    ef.strategies.append(noLT)
    ef.strategies.append(uraniumFRU)
    ef.apply_strategies()
    print(f"biosphere3 size: {len(bw2data.Database('biosphere3'))}")
    ef.statistics()

    # ef.write_excel(METHODNAME)
    # drop CFs which are not linked to a biosphere substance
    ef.drop_unlinked()
    # remove duplicates in exchanges
    for m in ef.data:
        m["exchanges"] = [
            dict(f) for f in list(set([frozendict(d) for d in m["exchanges"]]))
        ]

    ef.write_methods(overwrite=True)
    print(f"### Finished importing {METHODNAME}\n")


if __name__ == "__main__":
    setup_project()

    if len([method for method in bw2data.methods if method[0] == METHODNAME]) == 0:
        import_method()
    else:
        print(f"{METHODNAME} already imported")
