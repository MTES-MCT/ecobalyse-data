from __future__ import annotations

from typing import Any

import click
import orjson


@click.group(
    name="components",
    invoke_without_command=False,
    help="Manage application components.",
)
@click.pass_context
def component_management_group(_: dict[str, Any]) -> None:
    """Manage application components."""


@component_management_group.command(
    name="load-components", help="Load components from JSON file."
)
@click.argument(
    "json_file",
    type=click.File("rb"),
)
def load_components_json(json_file: click.File) -> None:
    """Promote to Superuser.

    Args:
        email (str): The email address of the user to promote.
    """

    from rich import get_console

    console = get_console()

    console.rule("Load components from JSON file.")

    json_data = orjson.loads(json_file.read())
    console.print_json(data=json_data)
