import json
import os

import bw2io
from bw2io.extractors import simapro_csv
from bw2io.importers.simapro_lcia_csv import SimaProLCIACSVExtractor
from bw2io.strategies import simapro


# We need to load a custom biosphere normalization file but the one that
# BW loads is harcoded in the `bw2io` code. So we need to patch the json_load function
# to load our own json file.
#
# Remember, don't try this at home, kids. This ugly hack was written by a professional.
def patched_load_json_data_file(filename):
    BW2IO_DATA_DIR = os.path.join(os.path.dirname(bw2io.utils.__file__), "data")
    CURRENT_FILE_DIR = os.path.dirname(__file__)

    if filename[-5:] != ".json":
        filename = filename + ".json"

    # If BW tries to load his bundled biosphere normalization, load our custom biosphere file instead
    if filename == "simapro-biosphere.json":
        # Use the simapro-biosphere.json from this repo
        filepath = os.path.join(CURRENT_FILE_DIR, "..", filename)
        print(f"#### Loading custom biosphere normalization from {filepath}")
    else:
        # Else load whatever BW wants to load from its data directory
        filepath = os.path.join(BW2IO_DATA_DIR, filename)

    return json.load(open(filepath, encoding="utf-8"))


# We add Normalization detection at it’s part of our CSV files
# https://github.com/ccomb/brightway2-io/commit/183b25d6bb224aea3939fd3bf77833d0759db327
def get_normalization_weighting_data(data, index):
    print("#### Custom `get_normalization_weighting_data`")

    nw_data = []
    name = data[index][0]
    index += 2
    assert data[index][0] == "Normalization"
    index += 1
    while data[index]:
        cat, norm = data[index][:2]
        index += 1
        if norm == "0":
            continue
        nw_data.append((cat, float(norm.replace(",", "."))))
    index += 1
    assert data[index][0] == "Weighting"
    index += 1
    while data[index]:
        cat, weight = data[index][:2]
        index += 1
        if weight == "0":
            continue
        nw_data.append((cat, float(weight.replace(",", "."))))
    return (name, nw_data), index


# https://github.com/ccomb/brightway2-io/commit/183b25d6bb224aea3939fd3bf77833d0759db327
def read_method_data_set(data, index, filepath):
    """
    Patch for `bw2io/extractors/simapro_lcia_csv.py`

    Normalization data seems
    """

    print("#### Custom `read_method_data_set`")

    metadata, index = SimaProLCIACSVExtractor.read_metadata(data, index)
    method_root_name = metadata.pop("Name")
    description = metadata.pop("Comment")
    category_data, nw_data, damage_category_data, completed_data = [], [], [], []

    # `index` is now the `Impact category` line
    while not data[index] or data[index][0] != "End":
        if not data[index] or not data[index][0]:
            index += 1
        elif data[index][0] == "Impact category":
            catdata, index = SimaProLCIACSVExtractor.get_category_data(data, index + 1)
            category_data.append(catdata)
        elif data[index][0] == "Normalization-Weighting set":
            nw_dataset, index = get_normalization_weighting_data(data, index + 1)
            nw_data.append(nw_dataset)
        elif data[index][0] == "Damage category":
            catdata, index = SimaProLCIACSVExtractor.get_damage_category_data(
                data, index + 1
            )
            damage_category_data.append(catdata)
        else:
            raise ValueError

    for ds in category_data:
        completed_data.append(
            {
                "description": description,
                "name": (method_root_name, ds[0]),
                "unit": ds[1],
                "filename": filepath,
                "exchanges": ds[2],
            }
        )

    return completed_data, index


simapro.load_json_data_file = patched_load_json_data_file
bw2io.load_json_data_file = patched_load_json_data_file

# @ccomb commit https://github.com/ccomb/brightway2-io/commit/3d3d9dea3cbfd212873eee1f757fecede6a3ec3f
simapro_csv.strip_whitespace_and_delete = lambda obj: (
    obj.replace("\x7f", "\n").strip() if isinstance(obj, str) else obj
)

SimaProLCIACSVExtractor.read_method_data_set = read_method_data_set
