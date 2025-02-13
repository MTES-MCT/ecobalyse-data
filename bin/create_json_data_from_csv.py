#!/usr/bin/env python3
import logging
import os
import tempfile
from pathlib import Path
import zipfile
from zipfile import ZipFile

import orjson
import typer
from bw2io.extractors.simapro_csv import SimaProCSVExtractor
from rich.logging import RichHandler
from typing_extensions import Annotated

# Use rich for logging
# @TODO: factor this code in a dedicated file
logger = logging.getLogger(__name__)
logger.setLevel(logging.INFO)
handler = RichHandler(markup=True)
handler.setFormatter(logging.Formatter(fmt="%(message)s", datefmt="[%X]"))
logger.addHandler(handler)

app = typer.Typer()


@app.command()
def create_all(
    overwrite: Annotated[
        bool,
        typer.Option(
            help="Should the output file be overwritten if it already exists."
        ),
    ] = False,
    zip: Annotated[
        bool,
        typer.Option(help="Should the output file be Gzipped."),
    ] = True,
):
    """
    Try to create json cache file for all our databases.
    """
    logger.error("❌ TODO")


@app.command()
def create_one(
    input_file: Annotated[
        typer.FileBinaryRead,
        typer.Argument(
            help="The input file containing the CSV data from Simapro. It can be a zipped file."
        ),
    ],
    db_name: Annotated[
        str,
        typer.Argument(help="Database name that will be used by Brightway."),
    ],
    output_json_file: Annotated[
        typer.FileBinaryWrite,
        typer.Argument(
            help="The output json file. If not specificed, the json will be outputed based on the input file name and directory."
        ),
    ] = None,
    overwrite: Annotated[
        bool,
        typer.Option(
            help="Should the output file be overwritten if it already exists."
        ),
    ] = False,
    zip: Annotated[
        bool,
        typer.Option(help="Should the output file be zipped."),
    ] = True,
    dry_run: Annotated[
        bool,
        typer.Option(
            help="Don’t apply changes. Use it to test what the script would really do."
        ),
    ] = False,
):
    input_path = Path(input_file.name)

    if output_json_file is not None:
        json_output_filename = output_json_file.name
    else:
        output_basename = os.path.join(
            os.path.dirname(input_file.name), input_path.stem
        )

        json_output_filename = f"{output_basename}.json"

    logger.info(f"🟢 Start json creation for '{input_file.name}'")

    logger.info(f"-> JSON output to '{json_output_filename}'")

    with tempfile.TemporaryDirectory() as tempdir:
        csv_file = input_file.name

        if input_path.suffix.lower() == ".zip":
            with ZipFile(input_file.name) as zf:
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

        with open(json_output_filename, "wb") as fp:
            extracted_data = {
                "data": data,
                "global_parameters": global_parameters,
                "metadata": metadata,
            }

            logger.info(f"-> Writing to json file {json_output_filename}")
            if not dry_run:
                fp.write(orjson.dumps(extracted_data))

    if zip:
        with ZipFile(
            f"{json_output_filename}.zip",
            "w",
            compression=zipfile.ZIP_DEFLATED,
            compresslevel=9,
        ) as zf:
            if not dry_run:
                zf.write(
                    json_output_filename, arcname=os.path.basename(json_output_filename)
                )

            logger.info(f"-> Zip file written to {json_output_filename}.zip")


if __name__ == "__main__":
    app()
