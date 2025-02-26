import atexit
import os
import shutil
import tempfile
from pathlib import Path

import bw2data
import wrapt
from bw2data import config
from bw2data.project import projects
from bw2io.backup import _extract_single_directory_tarball

from config import settings


@wrapt.decorator
def bw2test(wrapped, instance, args, kwargs):
    config.dont_warn = True
    config.is_test = True
    tempdir = Path(tempfile.mkdtemp())
    os.environ["BRIGHTWAY2_DIR"] = str(tempdir)

    projects.change_base_directories(
        base_dir=tempdir,
        base_logs_dir=tempdir,
        project_name=settings.bw.project,
        update=False,
    )
    projects._is_temp_dir = True
    atexit.register(shutil.rmtree, tempdir)
    bw2data.projects.set_current(settings.bw.project)
    return wrapped(*args, **kwargs)


def restore_archived_project(archive_path):
    with tempfile.TemporaryDirectory() as td:
        extracted_path = _extract_single_directory_tarball(
            filepath=Path(archive_path),
            output_dir=td,
        )

        base_data_dir, _ = projects._get_base_directories()

        shutil.copytree(extracted_path, base_data_dir, dirs_exist_ok=True)
