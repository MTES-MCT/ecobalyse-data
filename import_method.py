#!/usr/bin/env python3
import os
from os.path import dirname, join
from zipfile import ZipFile

import bw2data
import bw2io
from frozendict import frozendict

from common import brightway_patch as brightway_patch
from common.import_ import DB_FILES_DIR, setup_project
from config import settings

CURRENT_FILE_DIR = os.path.dirname(os.path.realpath(__file__))
# Agribalyse
METHODNAME = "Environmental Footprint 3.1 (adapted) patch wtu"  # defined inside the csv
METHODPATH = join(DB_FILES_DIR, METHODNAME + ".CSV.zip")

# excluded strategies and migrations
EXCLUDED = [
    "fix_localized_water_flows",
    "simapro-water",
]


def import_method(datapath=METHODPATH, biosphere=settings.bw.biosphere):
    """
    Import file at path `datapath` linked to biosphere named `dbname`
    """
    print(f"### Importing {datapath}...")

    # unzip
    with ZipFile(datapath) as zf:
        print("### Extracting the zip file...")
        zf.extractall(path=dirname(datapath))
        unzipped = datapath[0:-4]

    ef = bw2io.importers.SimaProLCIACSVImporter(
        unzipped,
        biosphere=biosphere,
        normalize_biosphere=True,
        # normalize_biosphere to align the categories between LCI and LCIA
    )

    os.unlink(unzipped)
    ef.statistics()

    # exclude strategies/migrations in EXCLUDED
    ef.strategies = [
        s for s in ef.strategies if not any([e in repr(s) for e in EXCLUDED])
    ]
    ef.apply_strategies()

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
