import os
from os.path import dirname

import bw2data
import orjson
import pytest
from bw2data import config as bwconfig
from bw2data import projects

from common import brightway_patch as brightway_patch
from config import settings
from ecobalyse_data.tests import restore_archived_project

PROJECT_ROOT_DIR = dirname(dirname(__file__))


@pytest.fixture(scope="session", autouse=True)
def set_test_settings():
    settings.configure(FORCE_ENV_FOR_DYNACONF="testing")


@pytest.fixture
def forwast(temp_bw_dir, set_test_settings):
    restore_archived_project(
        os.path.join(
            PROJECT_ROOT_DIR,
            "tests/fixtures/bw-project-forwast-with-patched-ef31.tar.gz",
        )
    )

    bw2data.projects.set_current(settings.bw.project)


@pytest.fixture
def temp_bw_dir(tmp_path):
    bwconfig.dont_warn = True
    bwconfig.is_test = True

    os.environ["BRIGHTWAY2_DIR"] = str(tmp_path)
    projects.change_base_directories(
        base_dir=tmp_path,
        base_logs_dir=tmp_path,
        project_name=settings.bw.project,
        update=False,
    )
    projects._is_temp_dir = True


@pytest.fixture
def forwast_json_icv():
    with open(os.path.join(PROJECT_ROOT_DIR, "tests/fixtures/forwast.json"), "rb") as f:
        return orjson.loads(f.read())


@pytest.fixture
def processes_food_json():
    with open(
        os.path.join(PROJECT_ROOT_DIR, "tests/fixtures/food/processes_impacts.json"),
        "rb",
    ) as f:
        return orjson.loads(f.read())


@pytest.fixture
def ingredients_food_json():
    with open(
        os.path.join(PROJECT_ROOT_DIR, "tests/fixtures/food/ingredients.json"),
        "rb",
    ) as f:
        return orjson.loads(f.read())
