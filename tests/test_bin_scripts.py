import tempfile

import bw2data
import orjson

from bin import export_bw_db, export_icv
from config import settings
from ecobalyse_data.bw import simapro_export


# Basic test to see if the script compiles
def test_export_icv(mocker):
    mocker.patch("bw2data.databases", return_value=[])

    with tempfile.NamedTemporaryFile(delete=False) as fp:
        # Just check that the main function runs as expected
        export_icv.main(output_file=fp, cpu_count=1, max=1)
        fp.close()

        # And that it creates an empty file
        with open(fp.name, "rb") as f:
            json_data = orjson.loads(f.read())
            assert json_data == {}


# Basic test to see if the script compiles
def test_export_icv_forwast(forwast, forwast_json_icv):
    with tempfile.NamedTemporaryFile(delete=False) as fp:
        # Just check that the main function runs as expected
        export_icv.main(
            project=settings.bw.project,
            output_file=fp,
            activity_name="_22 Vegetable and animal oils and fats, EU27",
            db=["forwast"],
        )
        fp.close()

        # And that it computes the expected data
        with open(fp.name, "rb") as f:
            json_data = orjson.loads(f.read())
            assert json_data == forwast_json_icv


def test_export_bw_db(mocker):
    # Just check that the imports are ok

    mocker.patch("ecobalyse_data.bw.simapro_export.export_db_to_simapro")
    with tempfile.NamedTemporaryFile(delete=False) as fp:
        export_bw_db.main(fp, "")
        simapro_export.export_db_to_simapro.assert_called_once()


def test_forwast_restore(forwast):
    assert list(bw2data.databases) == ["ecoinvent-3.9.1-biosphere", "forwast"]
