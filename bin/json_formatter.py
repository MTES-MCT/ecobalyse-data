#!/usr/bin/env -S uv run --script


import json
from pathlib import Path

import typer
from typing_extensions import Annotated, List

from ecobalyse_data.logging import logger

EXCLUDED_PATHS: List[str] = [
    "/.venv/",
    "/node_modules/",
    "/package.json",
    "/package-lock.json",
    "/tests/activities-schema.json",
    "/tests/processes-schema.json",
]


def _activities_sort_key(entry):
    return (
        entry.get("source", ""),
        entry.get("activityName", ""),
        entry.get("location"),
        entry.get("alias") or "",
        entry.get("displayName", ""),
    )


def _lint_and_fix(path: Path, fix: bool):
    logger.debug(f"Checking {path}")

    src_data = None
    with open(path, "r", encoding="utf-8") as fp:
        src_data = fp.read()
    assert src_data is not None

    input_data = json.loads(src_data)

    if path.name == "activities.json":
        input_data.sort(key=_activities_sort_key)

    formatted_data = json.dumps(
        input_data, ensure_ascii=False, sort_keys=True, indent=2
    )
    formatted_data += "\n"

    if formatted_data == src_data:
        logger.debug(f"{path} is already properly formatted")
        return True
    elif fix:
        logger.info(f"Reformatting {path}")
        with open(path, "w", encoding="utf-8") as fp:
            fp.write(formatted_data)
            return True
    logger.error(f"{path} needs formatting")
    return False


def is_excluded(path: Path):
    # TODO: starting with Python 3.13, we should be able to use
    # https://docs.python.org/3.13/library/pathlib.html#pathlib.PurePath.full_match
    # return any([path.full_match(exclusion) for exclusion in EXCLUDED_PATHS])
    return any(exclusion in str(path) for exclusion in EXCLUDED_PATHS)


def main(
    paths: Annotated[
        List[Path],
        typer.Argument(
            dir_okay=True,
            exists=True,
            writable=True,
            resolve_path=True,
            help="The paths of json files or of directories containing json files",
        ),
    ],
    fix: Annotated[
        bool,
        typer.Option(
            "--fix",
            help="Format the file(s) and write back the changes to the original file(s)",
        ),
    ] = False,
):
    """
    JSON formatter.

    By default, this will check that the files passed as arguments are properly formatted.
    With the --fix option, this will additionaly format them in place.
    """
    for path in paths:
        if is_excluded(path):
            logger.debug(f"ignoring {path}")
            continue
        if path.is_file():
            success = _lint_and_fix(path, fix)
            if not success:
                raise typer.Exit(-1)
        else:
            assert path.is_dir()
            json_files = path.glob("**/*.json")

            for json_file in json_files:
                if is_excluded(json_file):
                    logger.debug(f"ignoring {json_file}")
                    continue
                success = _lint_and_fix(json_file, fix)
                if not success:
                    raise typer.Exit(-1)


if __name__ == "__main__":
    typer.run(main)
