import os
import tempfile

import pytest

from common import brightway_patch as brightway_patch


@pytest.fixture
def temp_bw_dir():
    dirpath = tempfile.mkdtemp()
    os.environ["BRIGHTWAY2_DIR"] = dirpath
