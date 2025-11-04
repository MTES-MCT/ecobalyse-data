#!/usr/bin/env -S uv run --script
#
# /// script
# requires-python = ">=3.12"
# dependencies = ["pandas", "skimpy", "typer"]
# ///

import json
import textwrap
from pathlib import Path, PurePath

import pandas
import typer
from skimpy import clean_columns
from typing_extensions import Annotated

CURRENT_DIR = Path(__file__).parent.resolve()
DATA_DIR = CURRENT_DIR.parent / "public" / "data"


def clean_impacts(process: dict) -> dict:
    """Removes the empty impacts values."""
    impacts = process.pop("impacts")
    result = {**process, "impacts": {"ecs": impacts["ecs"], "pef": impacts["pef"]}}
    return result


def rearrange_keys(process: dict) -> dict:
    """Manually sort the columns to improve the readability of the data set."""
    return {
        "id": process["id"],
        "displayName": process["displayName"],
        "activityName": process["activityName"],
        "location": process["location"],
        "comment": process["comment"],
        "scopes": process["scopes"],
        "categories": process["categories"],
        "unit": process["unit"],
        "density": process["density"],
        "elecMJ": process["elecMJ"],
        "heatMJ": process["heatMJ"],
        "waste": process["waste"],
        "source": process["source"],
        "impacts": process["impacts"],
    }


def flatten_keys(process: dict) -> dict:
    """Flatten the processes to make them compatible with tabular formats."""
    impacts = process.pop("impacts")
    result = {
        **process,
        "scopes": "/".join(process["scopes"]),
        "categories": "/".join(process["scopes"]),
        "ecsImpact": impacts["ecs"],
        "pefImpact": impacts["pef"],
    }
    return result


def main(
    output_path: Annotated[
        Path,
        typer.Option(
            dir_okay=True,
            exists=True,
            writable=True,
            resolve_path=True,
            help="The absolute path of the directory where the generated files will be written.",
        ),
    ] = DATA_DIR / "export",
    file_prefix: Annotated[
        str,
        typer.Option(help="The filename (without extension) of the generated files."),
    ] = "ecobalyse-processes",
    dryrun: Annotated[
        bool,
        typer.Option(
            "--dry-run", "-n", help="Dry run. Will only show what would be done."
        ),
    ] = False,
):
    """
    Convert the `processes.json` file to the formats published on data.gouv.fr.
    """
    json_filename = PurePath(file_prefix).with_suffix(".json")
    parquet_filename = PurePath(file_prefix).with_suffix(".parquet")
    csv_filename = PurePath(file_prefix).with_suffix(".csv")

    if dryrun:
        print(
            textwrap.dedent(
                f"""
            Would write:

            - {json_filename}
            - {parquet_filename}
            - {csv_filename}

            to:
              {output_path}
            """
            )
        )
        return

    with open(DATA_DIR / "processes.json") as processes_fp:
        processes: list[dict] = [
            rearrange_keys(clean_impacts(process))
            for process in json.load(processes_fp)
        ]

        # Export the JSON version
        print(f"Writing {json_filename} to {output_path}")
        with open(output_path / json_filename, "w", encoding="utf-8") as json_fp:
            json.dump(processes, json_fp, indent=2, ensure_ascii=False)

        # Export the tabular versions
        flat_processes: list[dict] = [flatten_keys(process) for process in processes]

        # Load the flat processes inside Pandas, converting their keys to snake case
        df = clean_columns(pandas.DataFrame.from_records(flat_processes), case="snake")

        # Export the Parquet version
        print(f"Writing {parquet_filename} to {output_path}")
        df.to_parquet(output_path / parquet_filename, compression="zstd")

        # Export the CSV version
        print(f"Writing {csv_filename} to {output_path}")
        df.to_csv(output_path / csv_filename, sep=",", index=False, encoding="utf-8")

        print("Export done.")


if __name__ == "__main__":
    typer.run(main)
