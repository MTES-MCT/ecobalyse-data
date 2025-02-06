import collections
import sys
from bw2io.utils import activity_hash
import orjson

from typing import Tuple


def statistics(data, print_stats: bool = True) -> Tuple[int, int, int, int]:
    num_nodes = len(data)
    num_edges = sum(1 for ds in data for exc in ds.get("exchanges", []))
    num_unlinked = sum(
        [
            1
            for ds in data
            for exc in ds.get("exchanges", [])
            if not exc.get("input")
            and not (ds.get("type") == "multifunctional" and exc.get("functional"))
        ]
    )
    num_multifunctional = sum(1 for ds in data if ds.get("type") == "multifunctional")

    if print_stats:
        stats_nodes = "".join(
            f"\t{kind}: {count}\n"
            for kind, count in collections.Counter(
                ds.get("type") for ds in data
            ).most_common()
        )
        stats_edges = "".join(
            f"\t{kind}: {count}\n"
            for kind, count in collections.Counter(
                exc.get("type") for ds in data for exc in ds.get("exchanges", [])
            ).most_common()
        )
        stats_db_edges = "".join(
            f"\t{db}: {count}\n"
            for db, count in collections.Counter(
                exc["input"][0]
                for ds in data
                for exc in ds.get("exchanges", [])
                if "input" in exc
                and isinstance(exc["input"], tuple)
                and len(exc["input"])
            ).most_common()
        )

        uu = collections.defaultdict(set)
        for ds in data:
            for exc in (e for e in ds.get("exchanges", []) if not e.get("input")):
                print(exc["name"])
                uu[exc.get("type")].add(activity_hash(exc))
        stats_unlinked = "".join(
            f"\t{kind}: {count}\n"
            for kind, count in sorted(
                [(k, len(v)) for k, v in list(uu.items())], reverse=True
            )
        )
        num_unique_unlinked = sum(len(v) for v in uu.values())
    #         print(
    #             f"""-> Graph statistics for importer:
    # {num_nodes} graph nodes:
    # {stats_nodes}{num_edges} graph edges:
    # {stats_edges}{num_edges - num_unlinked} edges to the following databases:
    # {stats_db_edges}{num_unique_unlinked} unique unlinked edges ({num_unlinked} total):
    # {stats_unlinked}
    # """
    #         )
    return num_nodes, num_edges, num_unlinked, num_multifunctional


def debug_link(data):
    from bw2io.strategies.generic import link_technosphere_by_activity_hash

    return link_technosphere_by_activity_hash(data, fields=("name", "location", "unit"))


with open(sys.argv[1], "rb") as fp:
    data = orjson.loads(fp.read())
    # print(len(data))
    #
    statistics(data)
    # data = debug_link(data)
    # statistics(data)
