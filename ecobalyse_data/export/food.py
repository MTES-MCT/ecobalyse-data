from typing import Tuple

import bw2calc


def compute_land_occupation(bw_activity, land_occupation_method: Tuple[str, str, str]):
    lca = bw2calc.LCA({bw_activity: 1})
    lca.lci()
    lca.switch_method(land_occupation_method)
    lca.lcia()
    return float("{:.10g}".format(lca.score))
