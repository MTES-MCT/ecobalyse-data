import bw2data
import typer
from typing import Optional, List


def bw_databases_validation(values: Optional[List[str]]):
    available_bw_databases = ", ".join(bw2data.databases)

    for value in values:
        if value not in bw2data.databases:
            raise typer.BadParameter(
                f"Database not present in Brightway. Available databases are: {available_bw_databases}."
            )

    return values


def bw_database_validation(value: Optional[str]):
    if value:
        return bw_databases_validation([value])[0]

    return value
