from typing import Tuple

import bw2calc
from bw2data import get_multilca_data_objs

from ecobalyse_data.logging import logger

LAND_OCCUPATION_METHOD: Tuple[str, str, str] = (
    "selected LCI results",
    "resource",
    "land occupation",
)


def compute_land_occupation(
    bw_activity,
    land_occupation_method: Tuple[str, str, str] = LAND_OCCUPATION_METHOD,
):
    logger.debug(f"-> Computing land occupation for {bw_activity}")
    lca = bw2calc.LCA({bw_activity: 1})
    lca.lci()
    lca.switch_method(land_occupation_method)
    lca.lcia()
    logger.debug(f"-> Finished computing land occupation for {bw_activity} {lca.score}")

    return float(lca.score)


def compute_land_occupation_batch(bw_activities, chunk_size: int = 50) -> dict:
    """Batched equivalent of compute_land_occupation via MultiLCA."""
    unique = list({a.id: a for a in bw_activities}.values())
    if not unique:
        return {}

    method_config = {"impact_categories": [LAND_OCCUPATION_METHOD]}
    out = {}
    for i in range(0, len(unique), chunk_size):
        chunk = unique[i : i + chunk_size]
        demands = {str(a.id): {a.id: 1} for a in chunk}
        data_objs = get_multilca_data_objs(
            functional_units=demands, method_config=method_config
        )
        mlca = bw2calc.MultiLCA(
            demands=demands, method_config=method_config, data_objs=data_objs
        )
        mlca.lci()
        mlca.lcia()
        for (_method_t, fu_name), ci in mlca.characterized_inventories.items():
            out[int(fu_name)] = float(ci.sum())
    return out
