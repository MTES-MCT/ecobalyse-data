# Patch for https://github.com/brightway-lca/brightway2-io/pull/283
def lower_formula_parameters(db):
    """lower formula parameters"""
    for ds in db:
        for k in ds.get("parameters", {}).keys():
            if "formula" in ds["parameters"][k]:
                ds["parameters"][k]["formula"] = ds["parameters"][k]["formula"].lower()
    return db
