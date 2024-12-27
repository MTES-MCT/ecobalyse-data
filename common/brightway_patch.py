import json
import os

import bw2io
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


simapro.load_json_data_file = patched_load_json_data_file
bw2io.load_json_data_file = patched_load_json_data_file
