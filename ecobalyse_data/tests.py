import shutil
import tempfile
from pathlib import Path

from bw2data.project import projects
from bw2io.backup import _extract_single_directory_tarball


def restore_archived_project(archive_path):
    with tempfile.TemporaryDirectory() as td:
        extracted_path = _extract_single_directory_tarball(
            filepath=Path(archive_path),
            output_dir=td,
        )

        base_data_dir, _ = projects._get_base_directories()
        print(
            f"-> Restore archived project from {archive_path}, {extracted_path} to {base_data_dir}"
        )

        shutil.copytree(extracted_path, base_data_dir, dirs_exist_ok=True)
