from __future__ import annotations

from typing import Any

import click
import orjson


async def load_components_fixtures(components_data: dict) -> None:
    """Import/Synchronize Database Fixtures."""

    from app.config.app import alchemy
    from app.domain.components.services import ComponentService
    from structlog import get_logger

    logger = get_logger()
    async with ComponentService.new(config=alchemy, uniquify=True) as service:
        await service.upsert_many(
            match_fields=["name"], data=components_data, auto_commit=True, uniquify=True
        )
        await logger.ainfo("loaded components fixtures")


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

    import anyio
    from rich import get_console

    console = get_console()

    json_data = orjson.loads(json_file.read())

    async def _load_components_json(components_data) -> None:
        await load_components_fixtures(components_data)

    console.rule("Loading components file.")
    anyio.run(_load_components_json, json_data)
