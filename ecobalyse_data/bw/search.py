import functools
from typing import Optional

import bw2data

from ecobalyse_data.logging import logger


@functools.cache
def cached_search_one(
    dbname, search_terms, location=None, excluded_term=None
) -> Optional[dict]:
    return search_one(
        dbname, search_terms, location=location, excluded_term=excluded_term
    )


def search_one(
    dbname, search_terms, location=None, excluded_term=None
) -> Optional[dict]:
    """Search for a single activity in a Brightway database.

    Args:
        dbname (str): The name of the Brightway database to search in.
        search_terms (str): The search terms to use.
        location (str, optional): The location of the LCI (Country code like FR, BE, DE, or region like GLO, RoW, RER, etc.). Defaults to None.
        excluded_term (str, optional): The term to exclude from the search. Defaults to None.

    Returns:
        Brightway activity if exactly one exact match by name is found, otherwise raises a ValueError.
    """
    search_query = search_terms
    if location:
        search_query = search_query + f" {location}"
    results = bw2data.Database(dbname).search(search_query)

    if excluded_term:
        results = [res for res in results if excluded_term not in res["name"]]

    if not results:
        logger.warning(f"Not found in brightway db `{dbname}`: '{search_terms}'")
        return None

    exact_matches = []
    for result in results:
        result_name = result.get("name", "")
        result_location = result.get("location", "")

        # Check exact name match
        if result_name == search_terms:
            # If location specified, also check location match
            if location is None or result_location == location:
                exact_matches.append(result)

    if len(exact_matches) == 1:
        return exact_matches[0]
    else:
        results_string = "\n".join([str(result) for result in exact_matches])
        raise ValueError(
            f"This 'search' doesn’t return exactly one matching result by name (got {len(exact_matches)}) in database '{dbname}': {search_terms}.\nResults returned: {results_string}"
        )
