import os
import tempfile
from os.path import dirname

import bw2data
import orjson
import pytest

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
def temp_bw_dir():
    dirpath = tempfile.mkdtemp()
    os.environ["BRIGHTWAY2_DIR"] = dirpath


@pytest.fixture
def forwast_json_icv():
    with open(os.path.join(PROJECT_ROOT_DIR, "tests/fixtures/forwast.json"), "rb") as f:
        return orjson.loads(f.read())
