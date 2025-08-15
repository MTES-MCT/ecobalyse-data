from typing import List

from common import export as common_export
from common import (
    get_normalization_weighting_factors,
)
from common.export import (
    IMPACTS_JSON,
    display_changes_from_json,
    export_processes_to_dirs,
    format_json,
)
from common.impacts import impacts as impacts_py
from common.impacts import main_method
from ecobalyse_data.computation import compute_processes_for_activities
from ecobalyse_data.logging import logger
from models.process import ProcessWithMetadata, Scope


def activities_to_processes(
    activities: list[dict],
    aggregated_relative_file_path: str,
    impacts_relative_file_path: str,
    with_metadata_aggregated_relative_file_path: str,
    with_metadata_impacts_relative_file_path: str,
    dirs_to_export_to: List[str],
    graph_folder: str,
    plot: bool = False,
    display_changes: bool = True,
    simapro: bool = True,
    merge: bool = False,
    scopes: list[Scope] = None,
    cpu_count: int = 1,
):
    factors = get_normalization_weighting_factors(IMPACTS_JSON)

    processesWithMetadata: List[ProcessWithMetadata] = compute_processes_for_activities(
        activities,
        main_method,
        impacts_py,
        IMPACTS_JSON,
        factors,
        simapro=simapro,
        cpu_count=cpu_count,
    )

    if plot:
        common_export.plot_process_impacts(
            processesWithMetadata,
            graph_folder,
            main_method,
            impacts_py,
            IMPACTS_JSON,
            factors,
        )

    # Convert objects to dicts
    dumped_processes = [
        process.model_dump(
            by_alias=True, exclude={"bw_activity", "computed_by", "metadata"}
        )
        for process in processesWithMetadata
    ]

    # Convert objects to dicts
    # Exclude metadata for scopes 'veli' and 'object'
    dumped_processes_with_metadata = []
    for process in processesWithMetadata:
        scopes_values = [getattr(s, "value", s) for s in (process.scopes or [])]
        if any(s in ("veli", "object") for s in scopes_values):
            dumped = process.model_dump(
                by_alias=True, exclude={"bw_activity", "computed_by", "metadata"}
            )
        else:
            dumped = process.model_dump(
                by_alias=True, exclude={"bw_activity", "computed_by"}
            )
        dumped_processes_with_metadata.append(dumped)

    if display_changes:
        display_changes_from_json(
            processes_impacts_path=impacts_relative_file_path,
            processes_corrected_impacts=dumped_processes,
            # Compare by default with the first output dir
            dir=dirs_to_export_to[0],
        )

    exported_processes_files = export_processes_to_dirs(
        aggregated_relative_file_path,
        impacts_relative_file_path,
        dumped_processes,
        dirs_to_export_to,
        merge=merge,
        scopes=scopes,
    )

    exported_processes_with_metadata_files = export_processes_to_dirs(
        with_metadata_aggregated_relative_file_path,
        with_metadata_impacts_relative_file_path,
        dumped_processes_with_metadata,
        dirs_to_export_to,
        merge=merge,
        scopes=scopes,
    )

    format_json(" ".join(exported_processes_files))
    format_json(" ".join(exported_processes_with_metadata_files))

    logger.info("Export completed successfully.")
