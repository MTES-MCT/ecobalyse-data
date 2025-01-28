#!/usr/bin/env python3
import os
from os.path import dirname, join
from zipfile import ZipFile

import bw2data
import bw2io
from bw2data.project import projects
from frozendict import frozendict

from common import brightway_patch as brightway_patch
from common.import_ import (
    add_missing_substances,
)

CURRENT_FILE_DIR = os.path.dirname(os.path.realpath(__file__))
PROJECT = "ecobalyse"
# Agribalyse
BIOSPHERE = "biosphere3"
METHODNAME = "Environmental Footprint 3.1 (adapted) patch wtu"  # defined inside the csv
METHODPATH = join(CURRENT_FILE_DIR, "..", "dbfiles", METHODNAME + ".CSV.zip")

# excluded strategies and migrations
EXCLUDED = [
    "fix_localized_water_flows",
    "simapro-water",
]


def import_method(project, datapath=METHODPATH, biosphere=BIOSPHERE):
    """
    Import file at path `datapath` linked to biosphere named `dbname`
    """
    print(f"### Importing {datapath}...")
    projects.set_current(project)

    # unzip
    with ZipFile(datapath) as zf:
        print("### Extracting the zip file...")
        zf.extractall(path=dirname(datapath))
        unzipped = datapath[0:-4]

    # projects.create_project(project, activate=True, exist_ok=True)
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
    if PROJECT not in bw2data.projects:
        bw2io.remote.install_project("ecoinvent-3.9.1-biosphere", "ecobalyse")

    bw2data.projects.set_current(PROJECT)

    add_missing_substances(PROJECT, BIOSPHERE)

    if len([method for method in bw2data.methods if method[0] == METHODNAME]) == 0:
        import_method(PROJECT)
    else:
        print(f"{METHODNAME} already imported")
