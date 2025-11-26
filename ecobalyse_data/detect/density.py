from pathlib import Path

import pandas as pd
from rich.progress import track

import ecobalyse_data

from . import _name

# FAO Density DB initial version:
# https://www.fao.org/fileadmin/templates/food_composition/documents/density_DB_v2_0_final-1__1_.xlsx
DENSITYDB = Path(ecobalyse_data.__path__[0]) / Path("data", "density_DB.xlsx")
SHEET = "Density DB"
COLS = {"food": "A", "density": "B", "gravity": "C"}

# Language Model
MODEL = "all-MiniLM-L6-v2"
SCORE_KEY = "ingredientDensity_Score"
MATCH_KEY = "ingredientDensity_BestMatch"
THRESHOLD = 0.4  # stop on lower threshold
BAD, GOOD = 0.5, 0.7  # for coloring the debug output


def xls_to_df(xls_content):
    def col_letter_to_index(letter: str) -> int:
        return ord(letter.upper()) - ord("A")

    df_raw = pd.read_excel(xls_content, sheet_name=SHEET, engine="openpyxl")
    indices = [col_letter_to_index(COLS[key]) for key in COLS]
    df = df_raw.iloc[:, indices]
    df.columns = ["food", "density", "specific_gravity"]
    df = df[pd.notnull(df["density"]) | pd.notnull(df["specific_gravity"])]
    df = df.dropna(subset=["food"])
    return df


def _get(obj):
    return obj.get("density")


def _set(obj, density):
    obj["density"] = density
    return obj


class Detector:
    def __init__(self):
        """Get everything ready, to compute what we need"""
        # get the density database and transform to a dataframe
        print("Reading densities XLSX database...")
        self.densities_df = xls_to_df(DENSITYDB)

        print("Importing sentence_transformers...")  # takes time
        from sentence_transformers import SentenceTransformer

        print(f"loading the model: {MODEL}")
        self.model = SentenceTransformer(MODEL)

        # build the embeddings of the food names
        print("Computing embeddings of ingredient names...")
        self.food_names = self.densities_df["food"].tolist()
        self.food_embeddings = self.model.encode(self.food_names)

    def detect(
        self,
        ingredient,
        debug=False,
    ):
        "Return the best density found in the provided `densities_df` dataframe"
        "By comparing the vectorized ingredient name with the vectorized names of the density DB"
        "It returns the density found in the `density` column of the dataframe"
        "`name` column of the "
        "semantic match from the FAO Density DB. "
        "It uses sentence-transformers for similarity matching and supports caching for performance."
        # choose to build a sentence with the full json block
        sentence = _name(ingredient)

        # build the embedding of the sentence and query it
        query_embedding = self.model.encode(sentence, convert_to_tensor=True)
        similarities = self.model.similarity(query_embedding, self.food_embeddings)[0]
        best_idx = similarities.argmax().item()
        score = float(similarities[best_idx])
        best_match = self.food_names[best_idx]

        row = self.densities_df.iloc[best_idx]
        value = (
            row["density"] if pd.notnull(row["density"]) else row["specific_gravity"]
        )
        # turn value ranges into a mean: "0.2-0.4" → 0.3
        if isinstance(value, str) and "-" in value:
            value = sum(xs := [float(i) for i in value.split("-")]) / len(xs)
        assert isinstance(value, (int, float)), (
            f"Wrong value for `{row['food']}` in the reference data {DENSITYDB}"
        )
        return value, score, best_match


def update(input_json, threshold, debug=False):
    output_json = []

    detector = Detector()

    print("Trying to find densities for all ingredients:")
    for ingredient in track(input_json):
        if not _get(ingredient):
            continue

        value, score, best_match = detector.detect(ingredient, debug=False)

        if score >= threshold:
            _set(ingredient, value)
            if debug:
                ingredient[SCORE_KEY] = score
                ingredient[MATCH_KEY] = best_match
            else:
                if SCORE_KEY in ingredient:
                    del ingredient[SCORE_KEY]
                if MATCH_KEY in ingredient:
                    del ingredient[MATCH_KEY]
            output_json.append(ingredient)
        else:
            raise ValueError(
                f"❌ Low semantic match score for ingredient: '{_name(ingredient)}'"
                f"({score:.2f}) "
                f"Best match: '{best_match}'"
            )

    return output_json


def detect(input_json, threshold, debug=False):
    detector = Detector()
    return detector.detect(input_json, debug=False)
