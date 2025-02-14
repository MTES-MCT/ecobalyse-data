#!/usr/bin/env python3
import logging
import os
from pathlib import Path

import typer
from rich.logging import RichHandler
from typing_extensions import Annotated

from common.bw.simapro_json import export_csv_to_json

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
    output_json_file: Annotated[
        typer.FileBinaryWrite,
        typer.Argument(
            help="The output json file. If not specificed, the json will be outputed based on the input file name and directory."
        ),
    ] = None,
    db_name: Annotated[
        str | None,
        typer.Option(help="Database name that will be used by Brightway."),
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
    if output_json_file is not None:
        json_output_filename = output_json_file.name
    else:
        output_basename = os.path.join(
            os.path.dirname(input_file.name), Path(input_file.name).stem
        )

        json_output_filename = f"{output_basename}.json"

    return export_csv_to_json(
        input_file.name, json_output_filename, db_name=db_name, dry_run=dry_run
    )


if __name__ == "__main__":
    app()
