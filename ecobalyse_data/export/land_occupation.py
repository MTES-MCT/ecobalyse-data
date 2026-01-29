from typing import Tuple

import bw2calc

from ecobalyse_data.logging import logger


def compute_land_occupation(
    bw_activity,
    land_occupation_method: Tuple[str, str, str] = (
        "selected LCI results",
        "resource",
        "land occupation",
    ),
):
    logger.debug(f"-> Computing land occupation for {bw_activity}")
    lca = bw2calc.LCA({bw_activity: 1})
    lca.lci()
    lca.switch_method(land_occupation_method)
    lca.lcia()
    logger.debug(f"-> Finished computing land occupation for {bw_activity} {lca.score}")

    return float(lca.score)
