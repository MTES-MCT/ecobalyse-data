import functools
from typing import Optional

import bw2data

from ecobalyse_data.logging import logger


@functools.cache
def cached_search_one(dbname, search_terms, excluded_term=None) -> Optional[dict]:
    return search_one(dbname, search_terms, excluded_term)


def search_one(dbname, search_terms, excluded_term=None) -> Optional[dict]:
    results = bw2data.Database(dbname).search(search_terms)

    if excluded_term:
        results = [res for res in results if excluded_term not in res["name"]]

    if not results:
        logger.warning(f"Not found in brightway db `{dbname}`: '{search_terms}'")
        return None

    if len(results) > 1:
        # if the search gives more than one results, find the one with exact name
        exact_results = [a for a in results if a["name"] == search_terms]
        if len(exact_results) == 1:
            return exact_results[0]
        else:
            results_string = "\n".join([str(result) for result in results])
            raise ValueError(
                f"This 'search' doesn’t return exactly one matching result by name (got {len(exact_results)}) in database '{dbname}': {search_terms}.\nResults returned: {results_string}"
            )

    return results[0]


def search(dbname, search_terms, excluded_term=None):
    results = bw2data.Database(dbname).search(search_terms)
    if excluded_term:
        results = [res for res in results if excluded_term not in res["name"]]
    if not results:
        logger.warning(f"Not found in brightway db `{dbname}`: '{search_terms}'")
        return None
    if len(results) > 1:
        # if the search gives more than one results, find the one with exact name
        exact_results = [a for a in results if a["name"] == search_terms]
        if len(exact_results) == 1:
            return exact_results[0]
        else:
            results_string = "\n".join([str(result) for result in results])
            raise ValueError(
                f"This 'search' doesn’t return exactly one matching result by name ({len(exact_results)}) in database {dbname}: {search_terms}.\nResults returned: {results_string}"
            )
    return results[0]
