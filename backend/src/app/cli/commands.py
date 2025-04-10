from __future__ import annotations

from typing import Any

import click
import orjson


@click.group(
    name="fixtures",
    invoke_without_command=False,
    help="Manage application fixtures.",
)
@click.pass_context
def fixtures_management_group(_: dict[str, Any]) -> None:
    """Manage application components."""


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


@fixtures_management_group.command(
    name="load-components", help="Load components from JSON file."
)
@click.argument(
    "json_file",
    type=click.File("rb"),
)
def load_components_json(json_file: click.File) -> None:
    """Load components json.

    Args:
        component json file (Path): The path to the JSON file to load.
    """

    import anyio
    from rich import get_console

    console = get_console()

    json_data = orjson.loads(json_file.read())

    async def _load_components_json(components_data) -> None:
        await load_components_fixtures(components_data)

    console.rule("Loading components file.")
    anyio.run(_load_components_json, json_data)


async def load_processes_fixtures(processes_data: dict) -> None:
    """Import/Synchronize Database Fixtures."""

    from app.config.app import alchemy
    from app.domain.processes.services import ProcessService
    from structlog import get_logger

    logger = get_logger()
    async with ProcessService.new(config=alchemy, uniquify=True) as service:
        await service.upsert_many(
            match_fields=["name"], data=processes_data, auto_commit=True, uniquify=True
        )
        await logger.ainfo("loaded processes fixtures")


@fixtures_management_group.command(
    name="load-processes", help="Load processes from JSON file."
)
@click.argument(
    "json_file",
    type=click.File("rb"),
)
def load_processes_json(json_file: click.File) -> None:
    """Load processes json.

    Args:
        processes json file (Path): The path to the JSON file to load.
    """

    import anyio
    from rich import get_console

    console = get_console()

    json_data = orjson.loads(json_file.read())

    async def _load_processes_json(components_data) -> None:
        await load_processes_fixtures(components_data)

    console.rule("Loading processes file.")
    anyio.run(_load_processes_json, json_data)
