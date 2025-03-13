import os

import bw2data
import bw2io

from common import biosphere
from config import settings

CURRENT_FILE_DIR = os.path.dirname(os.path.realpath(__file__))


DB_FILES_DIR = os.getenv(
    "DB_FILES_DIR",
    os.path.join(CURRENT_FILE_DIR, "..", "..", "dbfiles"),
)


def init_project(
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
