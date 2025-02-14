import functools
import logging
import os
import tempfile
import zipfile
from pathlib import Path
from time import time

import orjson
from bw2data import Database, config
from bw2io.extractors.simapro_csv import SimaProCSVExtractor
from bw2io.importers.base_lci import LCIImporter
from bw2io.strategies import (
    assign_only_product_as_production,
    change_electricity_unit_mj_to_kwh,
    convert_activity_parameters_to_list,
    drop_unspecified_subcategories,
    fix_localized_water_flows,
    fix_zero_allocation_products,
    link_iterable_by_fields,
    link_technosphere_based_on_name_unit_location,
    migrate_datasets,
    migrate_exchanges,
    normalize_biosphere_categories,
    normalize_biosphere_names,
    normalize_simapro_biosphere_categories,
    normalize_simapro_biosphere_names,
    normalize_units,
    set_code_by_activity_hash,
    sp_allocate_products,
    split_simapro_name_geo,
    strip_biosphere_exc_locations,
    update_ecoinvent_locations,
)
from bw2io.strategies.simapro import set_lognormal_loc_value_uncertainty_safe
from rich.logging import RichHandler

# Use rich for logging
# @TODO: factor this code in a dedicated file
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = RichHandler(markup=True)
handler.setFormatter(logging.Formatter(fmt="%(message)s", datefmt="[%X]"))
logger.addHandler(handler)


def get_db_name(data):
    candidates = {obj["database"] for obj in data}
    if not len(candidates) == 1:
        raise ValueError("Can't determine database name from {}".format(candidates))
    return list(candidates)[0]


def export_csv_to_json(
    input_file: str, output_file: str, db_name: str | None = None, dry_run: bool = False
):
    logger.info(f"🟢 Start json creation for input file'{input_file}'")

    logger.info(f"-> JSON output to '{output_file}'")
    input_path = Path(input_file)

    with tempfile.TemporaryDirectory() as tempdir:
        csv_file = input_file

        # If the input is a zip file, extract it first
        if input_path.suffix.lower() == ".zip":
            with zipfile.ZipFile(input_file.name) as zf:
                logger.info(f"-> Extracting the zip file in {tempdir}...")
                csv_file = os.path.join(tempdir, input_path.stem)

                if not dry_run:
                    zf.extractall(path=tempdir)

        logger.info(f"-> Reading from CSV file '{csv_file}'…")

        data = []
        global_parameters = []
        metadata = []

        if not dry_run:
            data, global_parameters, metadata = SimaProCSVExtractor.extract(
                filepath=csv_file, name=db_name, delimiter=";", encoding="latin-1"
            )

        with open(output_file, "wb") as fp:
            extracted_data = {
                "data": data,
                "global_parameters": global_parameters,
                "metadata": metadata,
            }

            logger.info(f"-> Writing to json file {output_file}")
            if not dry_run:
                fp.write(orjson.dumps(extracted_data))

    if zip:
        with zipfile.ZipFile(
            f"{output_file}.zip",
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as zf:
            if not dry_run:
                zf.write(output_file, arcname=os.path.basename(output_file))

            logger.info(f"-> Zip file written to {output_file}.zip")


class SimaProJsonImporter(LCIImporter):
    format = "SimaPro Json"

    def __init__(
        self,
        filepath,
        name,
        delimiter=";",
        encoding="latin-1",
        normalize_biosphere=True,
        biosphere_db=None,
        extractor=SimaProCSVExtractor,
        json_file=None,
        write_json=False,
    ):
        start = time()

        # If we provide a json file and want to write to it, we extract data from the CSV
        # If we don’t povide a JSON file we extract data from the CSV as before
        if (
            export_to_json := (json_file is not None and write_json)
        ) or json_file is None:
            print(f"Extracting data from the CSV file {filepath}")

            self.data, self.global_parameters, self.metadata = extractor.extract(
                filepath=filepath,
                delimiter=delimiter,
                name=name,
                encoding=encoding,
            )
            print(
                "Extracted {} unallocated datasets in {:.2f} seconds".format(
                    len(self.data), time() - start
                )
            )

            if export_to_json:
                with open(json_file, "wb") as fp:
                    extracted_data = {
                        "data": self.data,
                        "global_parameters": self.global_parameters,
                        "metadata": self.metadata,
                    }

                    print(f"Writing to json file {json_file}")
                    fp.write(orjson.dumps(extracted_data))

        # If we provide a json_file but write_json in set to False,
        # we should try to read the data directly from the CSV
        if json_file is not None and not write_json:
            print(f"Reading from json file {json_file}")
            with open(json_file, "rb") as f:
                json_data = orjson.loads(f.read())
                self.data = json_data["data"]
                self.global_parameters = json_data["global_parameters"]
                self.metadata = json_data["metadata"]

        self.db_name = name

        self.strategies = [
            normalize_units,
            update_ecoinvent_locations,
            assign_only_product_as_production,
            drop_unspecified_subcategories,
            sp_allocate_products,
            fix_zero_allocation_products,
            split_simapro_name_geo,
            strip_biosphere_exc_locations,
            functools.partial(migrate_datasets, migration="default-units"),
            functools.partial(migrate_exchanges, migration="default-units"),
            functools.partial(set_code_by_activity_hash, overwrite=True),
            change_electricity_unit_mj_to_kwh,
            link_technosphere_based_on_name_unit_location,
            set_lognormal_loc_value_uncertainty_safe,
        ]
        if normalize_biosphere:
            self.strategies.extend(
                [
                    normalize_biosphere_categories,
                    normalize_simapro_biosphere_categories,
                    normalize_biosphere_names,
                    normalize_simapro_biosphere_names,
                    functools.partial(migrate_exchanges, migration="simapro-water"),
                    fix_localized_water_flows,
                ]
            )
        self.strategies.extend(
            [
                functools.partial(
                    link_iterable_by_fields,
                    other=Database(biosphere_db or config.biosphere),
                    kind="biosphere",
                ),
                convert_activity_parameters_to_list,
            ]
        )

    def write_database(self, data=None, name=None, *args, **kwargs):
        importer = super(SimaProJsonImporter, self)
        print(f"### -> Calling write_database with class {type(importer)}")
        db = importer.write_database(data, name, *args, **kwargs)
        db.metadata["simapro import"] = self.metadata
        db._metadata.flush()
        return db
