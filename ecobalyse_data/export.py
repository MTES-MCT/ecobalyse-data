import json
from typing import List

from frozendict import frozendict

from common.export import IMPACTS_JSON, export_processes_to_dirs, format_json
from common.impacts import impacts as impacts_py
from common.impacts import main_method
from ecobalyse_data.computation import compute_processes_for_activities
from ecobalyse_data.logging import logger
from models.process import Process


def get_activities_by_id(activities, logger) -> frozendict:
    logger.info("-> Get activities by id...")
    return frozendict({activity["id"]: activity for activity in activities})


def run(
    activities_path: str,
    aggregated_relative_file_path: str,
    impacts_relative_file_path: str,
    dirs_to_export_to: List[str],
    plot: bool = False,
    verbose: bool = False,
):
    logger.debug(f"-> Loading activities file {activities_path}")

    activities = []
    with open(activities_path, "r") as file:
        activities = json.load(file)

    processes: List[Process] = compute_processes_for_activities(
        activities, main_method, impacts_py, IMPACTS_JSON, logger
    )

    # Convert objects to dicts
    dumped_processes = [process.model_dump(by_alias=True) for process in processes]

    exported_files = export_processes_to_dirs(
        aggregated_relative_file_path,
        impacts_relative_file_path,
        dumped_processes,
        dirs_to_export_to,
    )

    format_json(" ".join(exported_files))

    logger.info("Export completed successfully.")
    # pprint(dumped_processes)
    # processes with impacts, impacts_simapro and impacts_brightway
    # processes_impacts = compute_impacts(
    #     activities, settings.bw.ecoinvent, impacts_py, IMPACTS_JSON, plot
    # )
