# density.py

from typing import Tuple, List
import pandas as pd
from sentence_transformers import util


def prepare_density_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Filters and renames the density DataFrame to only keep rows that contain either
    density or specific gravity.
    """
    df.columns = ["food", "density", "specific_gravity"]
    return df[pd.notnull(df["density"]) | pd.notnull(df["specific_gravity"])]


def lookup_density_semantic(
    input_string: str, df: pd.DataFrame, model
) -> Tuple[float, float, str]:
    """
    Returns the closest match for the input string using semantic embeddings.

    Args:
        input_string: string to match
        df: cleaned density DataFrame with 'food', 'density', 'specific_gravity'
        model: SentenceTransformer instance

    Returns:
        Tuple (density or specific_gravity, score, matched food label)
    """
    df = df.dropna(subset=["food"])
    food_names: List[str] = df["food"].tolist()
    food_embeddings = model.encode(food_names, convert_to_tensor=True)
    query_embedding = model.encode(input_string, convert_to_tensor=True)

    similarities = util.cos_sim(query_embedding, food_embeddings)[0]
    best_idx = similarities.argmax()
    best_score = float(similarities[best_idx])
    best_match = food_names[best_idx]

    row = df[df["food"] == best_match].iloc[0]
    value = row["density"] if pd.notnull(row["density"]) else row["specific_gravity"]
    return value, best_score, best_match

