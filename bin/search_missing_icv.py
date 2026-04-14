#!/usr/bin/env python3
"""Search for missing ICV names across all databases."""

import bw2data

from config import settings

bw2data.projects.set_current(settings.bw.PROJECT)

missing = [
    "Barley grain, non-irrigated, at farm (WFLDB)",
    "Sweet corn {US-MN}| sweet corn production | Cut-off, U",
    "Tomato, fresh grade, open field, at farm (WFLDB)",
    "Fava bean {CA-AB}| fava bean production | Cut-off, U",
    "Lettuce {GLO}| lettuce production, in heated greenhouse | Cut-off, U",
    "Walnut, in shell, dried, at farm (WFLDB)",
]

dbs = ["Agribalyse 3.2", "WFLDB", "Ginko 2025", "Ecoinvent 3.9.1"]

for name in missing:
    print(f"\n=== Searching: {name} ===")
    # Extract key words for search
    keywords = name.split(",")[0].split("{")[0].strip()
    for db in dbs:
        try:
            results = bw2data.Database(db).search(keywords, limit=5)
            if results:
                for r in results:
                    print(f"  [{db}] '{r['name']}' ({r.get('location', '?')})")
        except Exception:
            pass
