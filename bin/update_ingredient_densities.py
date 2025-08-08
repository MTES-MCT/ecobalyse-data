import argparse
import json
from io import BytesIO
from pathlib import Path, PurePosixPath
from urllib.parse import urlparse

import pandas as pd
import requests
from colorama import Fore, Style

DENSITYDB = "https://www.fao.org/fileadmin/templates/food_composition/documents/density_DB_v2_0_final-1__1_.xlsx"
SHEET = "Density DB"
COLS = {"food": "A", "density": "B", "gravity": "C"}
MODEL = "all-MiniLM-L6-v2"
FIELD = "ingredientDensity"
SCORE_KEY = "ingredientDensity_Score"
MARCH_KEY = "ingredientDensity_BestMatch"
BAD, GOOD = 0.5, 0.7


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


def update_json_with_density(
    input_json,
    model,
    densities_df,
    threshold,
    debug=False,
):
    output_json = []

    # build the embeddings of the food names
    print("Trying to find densities for all ingredients:")
    food_names = densities_df["food"].tolist()
    food_embeddings = model.encode(food_names, convert_to_tensor=True)

    for item in input_json:
        if FIELD not in item:
            continue

        # choose to build a sentence with the full json block
        sentence = item["search"]

        # build the embedding of the sentence
        query_embedding = model.encode(sentence, convert_to_tensor=True)
        similarities = util.cos_sim(query_embedding, food_embeddings)[0]
        best_idx = similarities.argmax().item()
        score = float(similarities[best_idx])
        best_match = food_names[best_idx]

        row = densities_df.iloc[best_idx]
        density = (
            row["density"] if pd.notnull(row["density"]) else row["specific_gravity"]
        )
        # turn value ranges into a mean: "0.2-0.4" → 0.3
        if type(density) is str and "-" in density:
            density = sum(xs := [float(i) for i in density.split("-")]) / len(xs)
        color = Fore.RED if score <= BAD else "" if score >= GOOD else Fore.YELLOW
        if debug:
            print(
                f"score: {color}{score:.2f}{Style.RESET_ALL} {item.get('displayName')} ~=> {best_match}"
            )
        else:
            print(".", end="")

        if score >= threshold:
            item[FIELD] = density
            if debug:
                item[SCORE_KEY] = score
                item[MARCH_KEY] = best_match
            else:
                if SCORE_KEY in item:
                    del item[SCORE_KEY]
                if MARCH_KEY in item:
                    del item[MARCH_KEY]
            output_json.append(item)
        else:
            raise ValueError(
                f"❌ Low semantic match score for ingredient: '{item.get('displayName')}'"
                f"({score:.2f}) "
                f"Best match: '{best_match}'"
            )

    return output_json


def download_if_needed(url, cachepath):
    cachefile = Path(cachepath, PurePosixPath(urlparse(url).path).name)
    if cachefile.exists():
        with open(cachefile, "rb") as f:
            return BytesIO(f.read())
    try:
        response = requests.get(url)
        response.raise_for_status()
    except requests.exceptions.HTTPError as e:
        print("❌ Download failed:", e)
        exit(1)

    if cachepath:
        Path(cachefile).write_bytes(response.content)

    return BytesIO(response.content)


if __name__ == "__main__":

    def dir_path(path):
        if Path(path).is_dir():
            return path
        else:
            raise NotADirectoryError(path)

    description = (
        f"This script updates the `{FIELD}` field in a JSON list of ingredient objects "
        "by finding the closest semantic match from the FAO Density DB. "
        "It uses sentence-transformers for similarity matching and supports caching for performance."
    )
    parser = argparse.ArgumentParser(description=description)
    parser.add_argument("input", type=argparse.FileType("r"), help="Input JSON file")
    parser.add_argument("output", type=argparse.FileType("w"), help="Output JSON file")
    parser.add_argument(
        "--cachepath",
        type=dir_path,
        default=Path.cwd(),
        help="Path to a download cache directory",
    )
    parser.add_argument(
        "--url", help="URL for the xlsx density database", default=DENSITYDB
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.5,
        help="Minimum similarity score to accept match",
    )
    parser.add_argument(
        "--debug",
        action="store_true",
        help="Include best match and score in output JSON",
    )
    args = parser.parse_args()

    # get the density database and transform to a dataframe
    densities_df = xls_to_df(download_if_needed(args.url, args.cachepath))

    print("Please wait a few seconds...")
    from sentence_transformers import SentenceTransformer, util

    output_json = update_json_with_density(
        input_json=json.load(args.input),
        model=SentenceTransformer(MODEL),
        threshold=args.threshold,
        debug=args.debug,
        densities_df=densities_df,
    )
    # save the output file
    args.output.write(json.dumps(output_json, indent=2, ensure_ascii=False))
    print(f"✅ Updated {len(output_json)} ingredients")
    if args.debug:
        mean = sum(s := [i[SCORE_KEY] for i in output_json]) / len(s)
        print(f"⚠️  Mean of all scores: {mean:.2f}")
