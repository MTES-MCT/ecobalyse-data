from pathlib import Path

import pandas
from rich.progress import track

import ecobalyse_data

from . import _name

# cooked/raw ratios for some food categories found in the Agribalyse doc
REFERENCE_DATA = Path(ecobalyse_data.__path__[0]) / Path("data", "cooked_to_raw.csv")

# Language Model
MODEL = "all-MiniLM-L6-v2"
SCORE_KEY = "cooked_to_raw_Ratio"
MATCH_KEY = "cooked_to_raw_BestMatch"
THRESHOLD = 0.4  # stop on lower threshold
BAD, GOOD = 0.5, 0.7  # for coloring the debug output


def _get(obj):
    return obj.get("rawToCookedRatio")


def _set(obj, value):
    obj["rawToCookedRatio"] = value


class Detector:
    def __init__(self):
        # get the reference database and transform to a dataframe
        print(f"Reading common cooked/raw ratios from {REFERENCE_DATA}...")
        self.dataframe = pandas.read_csv(REFERENCE_DATA, sep=";")

        print("Importing sentence_transformers...")  # takes time
        from sentence_transformers import SentenceTransformer

        print(f"loading the model: {MODEL}")
        self.model = SentenceTransformer(MODEL, local_files_only=True)

        # build the embeddings of the food names
        print("Computing embeddings of food names...")
        self.names = self.dataframe["food"].tolist()
        self.embeddings = self.model.encode(self.names)

    def detect(
        self,
        food,
        debug=False,
    ):
        "Return the best ratio found in the provided `dataframe`"
        "By comparing the vectorized food name with the vectorized names of the source DB"
        # choose a way to build a sentence
        sentence = _name(food)

        # build the embeddings of the sentence and query it
        embeddings = self.model.encode(sentence, convert_to_tensor=True)
        similarities = self.model.similarity(embeddings, self.embeddings)[0]
        best_idx = similarities.argmax().item()
        score = float(similarities[best_idx])
        best_match = self.names[best_idx]

        row = self.dataframe.iloc[best_idx]
        value = row["value"]
        return value, score, best_match


def update(input_json, threshold, debug=False):
    output_json = []

    detector = Detector()
    value = "Cooked/raw"

    print("Trying to find cooked/raw for all food ingredients:")
    for food in track(input_json, description=f"Detecting {value} values"):
        if not _get(food):
            continue

        value, score, best_match = detector.detect(food, debug=False)

        if score >= threshold:
            _set(food, value)
            if debug:
                food[SCORE_KEY] = score
                food[MATCH_KEY] = best_match
            else:
                if SCORE_KEY in food:
                    del food[SCORE_KEY]
                if MATCH_KEY in food:
                    del food[MATCH_KEY]
            output_json.append(food)
        else:
            raise ValueError(
                f"❌ Low semantic match score for food: '{_name(food)}'"
                f"({score:.2f}) "
                f"Best match: '{best_match}'"
            )

    return output_json


def detect(input_json, threshold, debug=False):
    detector = Detector()
    return detector.detect(input_json, debug=False)
