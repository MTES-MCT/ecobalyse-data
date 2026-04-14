#!/usr/bin/env python3
"""Check all CMAPS ICV names against Brightway databases and report mismatches."""

import json

import bw2data

from config import settings
from ecobalyse_data.bw.search import search_one

bw2data.projects.set_current(settings.bw.PROJECT)

with open("cmaps_activities_to_create.json") as f:
    entries = json.load(f)

corrections = {}
errors = []

for entry in entries:
    alias = entry["alias"]
    for ex in entry["exchanges"]:
        name = ex["name"]
        db = ex.get("database", entry["database"])
        location = ex.get("location")
        try:
            search_one(db, name, location=location)
        except ValueError as e:
            err_str = str(e)
            # Try to extract the suggested result
            if "Results returned:" in err_str:
                results_part = err_str.split("Results returned:\n")[1]
                # Extract first result name (format: 'Name' (unit, loc, code))
                if results_part.startswith("'"):
                    suggested = results_part.split("'")[1]
                    corrections[name] = suggested
                    print(f"MISMATCH [{db}]: {name}")
                    print(f"  -> {suggested}")
                else:
                    print(f"ERROR [{db}]: {name}")
                    print(f"  {err_str[:200]}")
                    errors.append((alias, name, db, err_str))
            elif "Not found" in err_str:
                print(f"NOT FOUND [{db}]: {name}")
                errors.append((alias, name, db, err_str))
            else:
                print(f"ERROR [{db}]: {name}")
                print(f"  {err_str[:200]}")
                errors.append((alias, name, db, err_str))

print("\n=== SUMMARY ===")
print(f"Corrections needed: {len(corrections)}")
print(f"Unresolvable errors: {len(errors)}")

if corrections:
    print("\n=== CORRECTIONS DICT (paste into script) ===")
    print("ICV_CORRECTIONS = {")
    for wrong, right in sorted(corrections.items()):
        print(f'    "{wrong}": "{right}",')
    print("}")
