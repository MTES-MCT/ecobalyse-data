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

    # Always filter for exact name match
    exact_results = [a for a in results if a["name"] == search_terms]

    if len(exact_results) == 1:
        return exact_results[0]

    # No exact match found - prepare error with closest match
    if not results:
        logger.warning(f"Not found in brightway db `{dbname}`: '{search_terms}'")
        return None

    # Show closest match (first fuzzy result) in error
    closest = results[0]
    raise ValueError(
        f"No exact match found for '{search_terms}' in database '{dbname}'. "
        f"Closest match: '{closest.get('name', 'Unknown')}' "
        f"(location: {closest.get('location', 'N/A')})"
    )
