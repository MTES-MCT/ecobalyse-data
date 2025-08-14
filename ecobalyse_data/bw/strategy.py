import copy
import re


# Patch for https://github.com/brightway-lca/brightway2-io/pull/283
def lower_formula_parameters(db):
    """lower formula parameters"""
    for ds in db:
        for k in ds.get("parameters", {}).keys():
            if "formula" in ds["parameters"][k]:
                ds["parameters"][k]["formula"] = ds["parameters"][k]["formula"].lower()
    return db


def organic_cotton_irrigation(db):
    """add irrigation to the organic cotton to be on par with conventional"""
    for ds in db:
        if ds.get("simapro metadata", {}).get("Process identifier") in (
            "MTE00149000081182217968",  # EI 3.9.1
            "EI3ARUNI000011519618166",  # EI 3.10
        ):
            # add: irrigation//[IN] market for irrigation;m3;0.75;Undefined;0;0;0;;
            ds["exchanges"].append({
                "amount": 0.75,
                "categories": ("Materials/fuels",),
                "comment": "",
                "loc": 0.75,
                "name": "irrigation//[IN] market for irrigation",
                "negative": False,
                "type": "technosphere",
                "uncertainty type": 2,
                "unit": "cubic meter",
            })
    return db


def remove_azadirachtine(db):
    """Remove all exchanges with azadirachtine, except for apples"""
    new_db = []
    for ds in db:
        new_ds = copy.deepcopy(ds)
        new_ds["exchanges"] = [
            exc
            for exc in ds["exchanges"]
            if (
                "azadirachtin" not in exc.get("name", "").lower()
                or ds.get("name", "").lower().startswith("apple")
            )
        ]
        new_db.append(new_ds)
    return new_db


def remove_negative_land_use_on_tomato(db):
    """Remove transformation flows from urban on greenhouses
    that cause negative land-use on tomatoes"""
    new_db = []
    for ds in db:
        new_ds = copy.deepcopy(ds)
        if ds.get("name", "").lower().startswith("plastic tunnel"):
            new_ds["exchanges"] = [
                exc
                for exc in ds["exchanges"]
                if not exc.get("name", "")
                .lower()
                .startswith("transformation, from urban")
            ]
        else:
            pass
        new_db.append(new_ds)
    return new_db


def fix_lentil_ldu(db):
    """Replace 'from unspecified' with 'from annual crop'
    to avoid having negative LDU on the lentils.
    Should be removed for AGB 3.2"""
    new_db = []
    for ds in db:
        new_ds = copy.deepcopy(ds)
        if ds.get("name", "").startswith("Lentil"):
            for exc in new_ds["exchanges"]:
                if exc.get("name", "").startswith("Transformation, from unspecified"):
                    exc["name"] = "Transformation, from annual crop"
        else:
            pass
        new_db.append(new_ds)
    return new_db


def remove_some_processes(db):
    """Some processes make the whole import fail
    due to inability to parse the Input and Calculated parameters"""
    new_db = []
    for ds in db:
        new_ds = copy.deepcopy(ds)
        if ds.get("simapro metadata", {}).get("Process identifier") not in (
            "EI3CQUNI000025017103662",
        ):
            new_db.append(new_ds)
    return new_db


def remove_creosote(db):
    """Remove creosote in unit treillis"""
    new_db = []
    for ds in db:
        new_ds = copy.deepcopy(ds)
        # The trellis is S on AGB, a bit deepter on WFLDB
        if "treillis" in ds["name"].lower():
            new_ds["exchanges"] = [
                exc
                for exc in ds["exchanges"]
                if "wood preservative, creosote" not in exc.get("name", "").lower()
            ]
        new_db.append(new_ds)
    return new_db


def remove_creosote_flows(db):
    """Remove creosote flows from flattened system trellis"""
    new_db = []
    for ds in db:
        new_ds = copy.deepcopy(ds)
        # The trellis is S on AGB, a bit deepter on WFLDB
        if "trellis" in ds["name"].lower():
            new_ds["exchanges"] = [
                exc
                for exc in ds["exchanges"]
                if (exc.get("name", "") != "Benzo(a)pyrene")
            ]
        new_db.append(new_ds)
    return new_db


def remove_acetamiprid(db):
    """Remove acetamiprid in FR activities"""
    new_db = []
    for ds in db:
        new_ds = copy.deepcopy(ds)
        if new_ds["location"] == "FR":
            new_ds["exchanges"] = [
                exc for exc in ds["exchanges"] if exc.get("name", "") != "Acetamiprid"
            ]
        new_db.append(new_ds)
    return new_db


def use_unit_processes(db):
    """the woolmark dataset comes with dependent processes
    which are set as system processes.
    Ecoinvent has these processes but as unit processes.
    So we change the name so that the linking be done"""
    for ds in db:
        for exc in ds["exchanges"]:
            if exc["name"].endswith(" | Cut-off, S"):
                exc["name"] = exc["name"].replace(" | Cut-off, S", "")
                exc["name"] = re.sub(
                    r" \{([A-Za-z]{2,3})\}\| ", r"//[\1] ", exc["name"]
                )
    return db


def uraniumFRU(db):
    """reduce the FRU of Uranium"""
    new_db = []
    for method in db:
        new_method = copy.deepcopy(method)
        if new_method["name"][1] == "Resource use, fossils":
            for k, v in new_method.items():
                if k == "exchanges":
                    for cf in v:
                        if cf["name"].startswith("Uranium"):
                            # lower by 40%
                            cf["amount"] *= 1 - 0.4
        new_db.append(new_method)
    return new_db


def noLT(db):
    """exclude long term impacts"""
    new_db = []
    for method in db:
        new_method = copy.deepcopy(method)
        for k, v in new_method.items():
            if k == "exchanges":
                for cf in v:
                    if any(["long-term" in cat for cat in cf["categories"]]):
                        cf["amount"] = 0
        new_db.append(new_method)
    return new_db


def extract_name_location_product(db):
    """extract the product, name and location from
    ecoinvent passing in SimaPro"""
    pattern = re.compile(r"^(?P<product>.+?)//\[(?P<cc>[^\]]+)\]\s*(?P<activity>.+)$")
    for ds in db:
        name = pattern.match(ds["name"].strip())
        if not name:
            raise ValueError(f"Unexpected activity name: {name!r}")
        ds["location"] = name.group("cc").strip()
        ds["reference product"] = name.group("product").strip()
    return db
