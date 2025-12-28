"""
ecobalyse_data/detect/predict.py
================================

Predicts ALL metadata for a new ingredient from:
- Its name (French or English)
- Its LCA process name (activityName)

Uses classifiers trained on existing ingredients.

Usage:
    from ecobalyse_data.detect import predict

    # Training (once)
    predictor = predict.Predictor()
    predictor.fit(existing_ingredients)  # list of dicts
    predictor.save("models/ingredient_predictor.pkl")

    # Prediction
    predictor = predict.Predictor.load("models/ingredient_predictor.pkl")
    new_ingredient = {
        "name": "Tomate cerise bio",
        "activityName": "Cherry tomato, organic {FR} U"
    }
    predictions = predictor.predict(new_ingredient)
    # -> {"foodType": "vegetable", "density": 1.0, "densityMatch": {"file": "...", "name": "...", "confidence": 0.95}, ...}

CLI:
    # Train on existing ingredients
    python -m ecobalyse_data.detect.predict train ingredients.json --output model.pkl

    # Predict for a new ingredient
    python -m ecobalyse_data.detect.predict infer model.pkl --name "Tomate cerise" --activity "Cherry tomato {FR} U"

    # Evaluate with cross-validation
    python -m ecobalyse_data.detect.predict evaluate ingredients.json
"""

import json
import math
import pickle
import re
import time
import warnings
from pathlib import Path
from typing import Optional

import numpy as np
import pandas as pd
import torch
from sklearn.ensemble import RandomForestClassifier
from sklearn.model_selection import cross_val_score
from sklearn.preprocessing import LabelEncoder
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

warnings.filterwarnings("ignore")

# =============================================================================
# CONFIGURATION
# =============================================================================


# Noise words to remove from ingredient names before embedding
# Case-insensitive words
NAME_NOISE_WORDS_CI = [
    "par défaut",
    "par defaut",
    "élec",
]
# Case-sensitive words (uppercase country codes)
NAME_NOISE_WORDS_CS = [
    "FR",
    "IT",
    "DE",
    "ES",
    "BE",
    "UE",
    "EU",
]


def cleanup_name(name: str) -> str:
    """Remove noise words (country codes, 'par défaut', etc.) from ingredient name."""
    s = name
    # Case-insensitive removal
    pattern_ci = r"\b(" + "|".join(NAME_NOISE_WORDS_CI) + r")\b"
    s = re.sub(pattern_ci, " ", s, flags=re.IGNORECASE)
    # Case-sensitive removal (uppercase country codes only)
    pattern_cs = r"\b(" + "|".join(NAME_NOISE_WORDS_CS) + r")\b"
    s = re.sub(pattern_cs, " ", s)
    # Clean up punctuation and multiple spaces
    s = re.sub(r"[|]", " ", s)
    s = re.sub(r"\s+", " ", s)
    return s.strip(" ,;-").strip()


# Translation cache file (persisted to disk for faster subsequent runs)
TRANSLATION_CACHE_PATH = Path(__file__).parent / ".translation_cache.pkl"
MT_MODEL = "Helsinki-NLP/opus-mt-fr-en"  # FR → EN Machine Translation
# Embedding model (used for evaluation cross-validation only)
MODEL = "all-MiniLM-L6-v2"

# Base categories (legacy - kept for backward compatibility during training)
BASE_CATEGORIES = [
    "misc",
    "dairy_product",
    "vegetable_processed",
    "vegetable_fresh",
    "grain_processed",
    "spice_condiment_additive",
    "animal_product",
    "nut_oilseed_raw",
    "grain_raw",
    "nut_oilseed_processed",
]

# New dimensional approach: split categories into foodType + processingState
FOOD_TYPES = [
    "vegetable",
    "fruit",
    "grain",
    "nut_oilseed",
    "dairy",
    "meat",
    "fish_seafood",
    "spice_condiment",
    "beverage",
    "misc",
]

PROCESSING_STATES = ["raw", "processed"]

# Mapping from old categories to new dimensions (foodType, processingState)
CATEGORY_TO_DIMENSIONS = {
    "vegetable_fresh": ("vegetable", "raw"),
    "vegetable_processed": ("vegetable", "processed"),
    "grain_raw": ("grain", "raw"),
    "grain_processed": ("grain", "processed"),
    "nut_oilseed_raw": ("nut_oilseed", "raw"),
    "nut_oilseed_processed": ("nut_oilseed", "processed"),
    "dairy_product": ("dairy", "processed"),
    "animal_product": ("meat", "raw"),
    "spice_condiment_additive": ("spice_condiment", "processed"),
    "misc": ("misc", "processed"),
}

# Reverse mapping: (foodType, processingState) -> base category
DIMENSIONS_TO_CATEGORY = {
    ("vegetable", "raw"): "vegetable_fresh",
    ("vegetable", "processed"): "vegetable_processed",
    ("fruit", "raw"): "vegetable_fresh",  # Fruits use vegetable_fresh in Ecobalyse
    ("fruit", "processed"): "vegetable_processed",
    ("grain", "raw"): "grain_raw",
    ("grain", "processed"): "grain_processed",
    ("nut_oilseed", "raw"): "nut_oilseed_raw",
    ("nut_oilseed", "processed"): "nut_oilseed_processed",
    ("dairy", "raw"): "dairy_product",
    ("dairy", "processed"): "dairy_product",
    ("meat", "raw"): "animal_product",
    ("meat", "processed"): "animal_product",
    ("fish_seafood", "raw"): "animal_product",
    ("fish_seafood", "processed"): "animal_product",
    ("spice_condiment", "raw"): "spice_condiment_additive",
    ("spice_condiment", "processed"): "spice_condiment_additive",
    ("beverage", "raw"): "misc",
    ("beverage", "processed"): "misc",
    ("misc", "raw"): "misc",
    ("misc", "processed"): "misc",
}

# Packaging types with their keywords and transportCooling values
PACKAGING_PATTERNS = {
    "canned": (r"\b(conserve|canned|appertis[ée]|bo[iî]te|tin)\b", "none"),
    "dried": (r"\b(s[ée]ch[ée]|d[ée]shydrat[ée]|dried|dehydrated|sec)\b", "none"),
    "frozen": (r"\b(surgel[ée]|congel[ée]|frozen)\b", "always"),
    "jar": (r"\b(bocal|jar|pot)\b", "none"),
    "vacuum": (r"\b(sous.?vide|vacuum)\b", "once_transformed"),
    "ambient": (r"\b(ambiant|ambient|shelf.?stable)\b", "none"),
    "fresh": (r"\b(frais|fra[iî]che|fresh)\b", None),  # None = depends on foodType
}

# Additive labels (can combine with a base category)
ADDITIVE_LABELS = ["organic", "bleublanccoeur"]

TRANSPORT_COOLING_VALUES = ["none", "always", "once_transformed"]

# Mapping location -> origin
ORIGIN_MAPPING = {
    "FR": "France",
    "IT": "EuropeAndMaghreb",
    "ES": "EuropeAndMaghreb",
    "DE": "EuropeAndMaghreb",
    "BE": "EuropeAndMaghreb",
    "NL": "EuropeAndMaghreb",
    "PT": "EuropeAndMaghreb",
    "GR": "EuropeAndMaghreb",
    "PL": "EuropeAndMaghreb",
    "AT": "EuropeAndMaghreb",
    "DZ": "EuropeAndMaghreb",  # Algérie
    "MA": "EuropeAndMaghreb",  # Maroc
    "TN": "EuropeAndMaghreb",  # Tunisie
    "GLO": "OutOfEuropeAndMaghreb",
    "RoW": "OutOfEuropeAndMaghreb",
    "WI": "OutOfEuropeAndMaghreb",  # West Indies
    "BR": "OutOfEuropeAndMaghreb",
    "CN": "OutOfEuropeAndMaghreb",
    "IN": "OutOfEuropeAndMaghreb",
    "US": "OutOfEuropeAndMaghreb",
}


# =============================================================================
# REFERENCE DATA FOR VALUE CLASSIFIERS
# =============================================================================

# Paths to reference data files (relative to predict module)
REFERENCE_DIR = Path(__file__).parent / "reference"


def _load_csv_data(
    path: Path,
    name_col: str = "name",
    value_col: str = None,
    sep: str = ",",
    comment: str = None,
) -> tuple[list, list, list]:
    """
    Generic CSV loader returning (names, values, sources).

    Args:
        path: Path to CSV file
        name_col: Column name for names
        value_col: Column name for values (if None, uses names as values)
        sep: CSV separator
        comment: Comment character for CSV parsing
    """
    if not path.exists():
        return [], [], []
    df = pd.read_csv(path, sep=sep, comment=comment)
    names = df[name_col].tolist()
    values = df[value_col].tolist() if value_col else names
    sources = [path.name] * len(df)
    return names, values, sources


def _load_density_data() -> tuple[list, list, list]:
    """Load fao_density.csv and density.csv, return combined (names, values, sources)."""
    names, values, sources = [], [], []
    # FAO density (primary reference)
    n, v, s = _load_csv_data(
        REFERENCE_DIR / "fao_density.csv", "name", "density", sep=";"
    )
    names.extend(n)
    values.extend(v)
    sources.extend(s)
    # Generic density (additional reference)
    n, v, s = _load_csv_data(REFERENCE_DIR / "density.csv", "name", "density", sep=";")
    names.extend(n)
    values.extend(v)
    sources.extend(s)
    return names, values, sources


def _load_inedible_data() -> tuple[list, list, list]:
    """Load agb_inedible.csv and inedible_part.csv, return combined (names, values, sources)."""
    names, values, sources = [], [], []
    # AGB inedible (primary reference)
    n, v, s = _load_csv_data(
        REFERENCE_DIR / "agb_inedible.csv", "name", "inedible_part", sep=";"
    )
    names.extend(n)
    values.extend(v)
    sources.extend(s)
    # Generic inedible (additional reference)
    n, v, s = _load_csv_data(
        REFERENCE_DIR / "inedible_part.csv", "name", "inedible_part", sep=";"
    )
    names.extend(n)
    values.extend(v)
    sources.extend(s)
    return names, values, sources


def _load_ratio_data() -> tuple[list, list, list]:
    """Load cooked_to_raw.csv, return (names, values, sources)."""
    return _load_csv_data(REFERENCE_DIR / "cooked_to_raw.csv", "food", "value", sep=";")


def _load_food_type_data() -> tuple[list, list, list]:
    """Load food_type.csv, return (names, food_types, sources)."""
    return _load_csv_data(REFERENCE_DIR / "food_type.csv", "name", "foodType")


def _load_processing_state_data() -> tuple[list, list, list]:
    """Load processing_state.csv, return (names, processing_states, sources)."""
    return _load_csv_data(
        REFERENCE_DIR / "processing_state.csv", "name", "processingState"
    )


def _load_cropgroup_data() -> tuple[list, list, list]:
    """Load cropgroup.csv, return (names, cropgroups, sources)."""
    return _load_csv_data(
        REFERENCE_DIR / "cropgroup.csv", "name", "cropGroup", comment="#"
    )


def _load_transport_data() -> tuple[list, list, list]:
    """Load transport_cooling.csv, return (names, transport_cooling, sources)."""
    return _load_csv_data(
        REFERENCE_DIR / "transport_cooling.csv", "name", "transportCooling"
    )


def _build_cropgroup_data(ingredients: list) -> tuple[list, list, list]:
    """Build (names, cropGroups, sources) from training ingredients + cropGroup labels themselves."""
    names = []
    cropgroups = []
    sources = []

    # Add ingredient names as training points
    for ing in ingredients:
        if ing.get("cropGroup"):
            names.append(ing.get("name", ""))
            cropgroups.append(ing["cropGroup"])
            sources.append("ingredients.json")

    # Add cropGroup labels themselves as training points
    # e.g., "LEGUMES-FLEURS" → LEGUMES-FLEURS
    unique_cropgroups = set(cropgroups)
    for cg in unique_cropgroups:
        names.append(cg)  # The label itself
        cropgroups.append(cg)
        sources.append("cropgroup_labels")

    return names, cropgroups, sources


def _extract_ingredient_values(
    ingredients: list, field: str, allow_zero: bool = False
) -> tuple[list, list, list]:
    """
    Extract (names, values, sources) from ingredients with a given field.

    Args:
        ingredients: List of ingredient dicts
        field: Field name to extract (e.g., "ingredientDensity", "inediblePart")
        allow_zero: If True, include zero values (use "is not None" check).
                   If False, exclude zero/falsy values (use truthiness check).
    """
    if allow_zero:
        # Use "is not None" check to include zero values
        names = [ing["name"] for ing in ingredients if ing.get(field) is not None]
        values = [ing[field] for ing in ingredients if ing.get(field) is not None]
    else:
        # Use truthiness check to exclude zero/falsy values
        names = [ing["name"] for ing in ingredients if ing.get(field)]
        values = [ing[field] for ing in ingredients if ing.get(field)]
    sources = ["ingredients.json"] * len(names)
    return names, values, sources


class NearestNeighborMatcher:
    """Find nearest neighbor by cosine similarity using FoodOn + regex features."""

    def __init__(
        self,
        names: list,
        values: list,
        sources: list = None,
        translate_fn=None,
        foodon_extractor=None,
    ):
        """
        Build a nearest neighbor matcher on FoodOn + regex features.

        Args:
            names: List of food names from reference data
            values: List of corresponding values (numeric or string)
            sources: List of source file names (e.g., "fao_density.csv", "ingredients.json")
            translate_fn: Optional function to translate names before encoding
            foodon_extractor: Optional FoodOnFeatureExtractor for ontology features
        """
        self.names = list(names)
        self.values = list(values)  # Keep as list to support both numeric and string
        self.sources = list(sources) if sources else ["unknown"] * len(names)
        self.foodon_extractor = foodon_extractor
        self.translate_fn = translate_fn

        # Translate names if translation function provided (cached)
        translated_names = list(names)
        if translate_fn:
            print(f"  Translating {len(names)} names (cached)...")
            translated_names = [translate_fn(n) for n in names]

        # Store both original and translated names (lowercase) for text matching
        self.names_lower = [n.lower() for n in names]
        self.translated_lower = [n.lower() for n in translated_names]

        # Compute FoodOn + regex features for all reference names
        print(f"  Computing FoodOn+regex features for {len(names)} reference items...")
        features_list = []
        for i, name in enumerate(names):
            feat = extract_features(
                translated_names[i],
                "",
                translate_fn=None,  # Already translated
                foodon_extractor=foodon_extractor,
            )
            features_list.append(feat)
        self.features = np.array(features_list)
        print(f"  Nearest neighbor matcher ready ({len(names)} items)")

    def predict(self, query: str, translate_fn=None, foodon_extractor=None):
        """
        Find nearest neighbor and return its value.

        Priority:
        1. Exact text match (case-insensitive)
        2. Substring match (query contains reference or vice versa)
        3. FoodOn + regex feature similarity

        Args:
            query: Query string (ingredient name)
            translate_fn: Optional translation function
            foodon_extractor: Optional FoodOn extractor (uses stored one if not provided)

        Returns:
            (value, confidence, best_match_name, source) - value can be numeric or string
        """
        # Use stored values if not provided
        extractor = (
            foodon_extractor if foodon_extractor is not None else self.foodon_extractor
        )
        translator = translate_fn if translate_fn is not None else self.translate_fn

        # Normalize query for text matching
        query_lower = query.lower()
        query_translated = translator(query).lower() if translator else query_lower

        # 1. Try exact text match first (original or translated)
        for i, (name_low, trans_low) in enumerate(
            zip(self.names_lower, self.translated_lower)
        ):
            if query_lower == name_low or query_translated == trans_low:
                value = self.values[i]
                if isinstance(value, (int, float, np.number)):
                    value = float(value)
                return value, 1.0, self.names[i], self.sources[i]

        # 2. Try substring match (prioritize longer matches, min 4 chars to avoid false matches)
        MIN_SUBSTRING_LENGTH = 4
        substring_matches = []
        for i, (name_low, trans_low) in enumerate(
            zip(self.names_lower, self.translated_lower)
        ):
            # Check if reference name is contained in query (min length required)
            if len(name_low) >= MIN_SUBSTRING_LENGTH and name_low in query_lower:
                substring_matches.append((i, len(name_low)))
            elif (
                len(trans_low) >= MIN_SUBSTRING_LENGTH and trans_low in query_translated
            ):
                substring_matches.append((i, len(trans_low)))
            # Check if query is contained in reference (min length required)
            elif len(query_lower) >= MIN_SUBSTRING_LENGTH and query_lower in name_low:
                substring_matches.append((i, len(query_lower)))
            elif (
                len(query_translated) >= MIN_SUBSTRING_LENGTH
                and query_translated in trans_low
            ):
                substring_matches.append((i, len(query_translated)))

        if substring_matches:
            # Return the longest substring match
            best_i, _ = max(substring_matches, key=lambda x: x[1])
            value = self.values[best_i]
            if isinstance(value, (int, float, np.number)):
                value = float(value)
            return value, 0.95, self.names[best_i], self.sources[best_i]

        # 3. Fall back to FoodOn + regex feature similarity
        query_features = extract_features(
            query, "", translate_fn=translator, foodon_extractor=extractor
        ).reshape(1, -1)

        # Compute cosine similarities to all reference features
        similarities = np.dot(self.features, query_features.T).flatten()
        norms_ref = np.linalg.norm(self.features, axis=1)
        norm_query = np.linalg.norm(query_features)
        # Avoid division by zero
        valid_norms = (norms_ref > 0) & (norm_query > 0)
        similarities[valid_norms] = similarities[valid_norms] / (
            norms_ref[valid_norms] * norm_query
        )
        similarities[~valid_norms] = 0

        # Return value of closest match
        best_idx = int(np.argmax(similarities))
        value = self.values[best_idx]
        # Convert to float if numeric, otherwise keep as string
        if isinstance(value, (int, float, np.number)):
            value = float(value)
        return (
            value,
            float(similarities[best_idx]),
            self.names[best_idx],
            self.sources[best_idx],
        )


# =============================================================================
# FEATURE EXTRACTION
# =============================================================================

# Detection patterns (French + English)
DETECTION_PATTERNS = {
    # Processing attributes
    "is_organic": r"\b(bio|organic|organique)\b",
    "is_fresh": r"\b(frais|fraîche|fraiche|fresh)\b",
    "is_frozen": r"\b(surgelé|surgelee|congelé|congelee|frozen)\b",
    "is_cooked": r"\b(cuit|cuite|cuire|cooked|roasted|grillé|grillee|rôti|rotie|bouilli|poché|pochee|frit|frite)\b",
    "is_raw": r"\b(cru|crue|raw|brut|brute)\b",
    "is_dried": r"\b(séché|sechee|sec|sèche|seche|dried|déshydraté|deshydratee)\b",
    "is_processed": r"\b(transformé|transformee|processed|préparé|preparee|industriel|conserve)\b",
    "is_canned": r"\b(conserve|appertisé|appertisee|canned)\b",
    "is_smoked": r"\b(fumé|fumee|smoked)\b",
    # Food types - Animals
    "is_meat": r"\b(viande|meat|boeuf|beef|porc|pork|veau|veal|agneau|lamb|mouton|mutton|poulet|chicken|dinde|turkey|canard|duck|lapin|rabbit|gibier|game)\b",
    "is_fish": r"\b(poisson|pêche|fish|cabillaud|cod|saumon|salmon|thon|tuna|sardine|maquereau|mackerel|truite|trout|bar|bass|dorade|bream|merlu|hake|sole|anchois|anchovy)\b",
    "is_seafood": r"\b(fruit.{0,3}mer|seafood|crevette|shrimp|prawn|crabe|crab|homard|lobster|moule|mussel|huître|huitre|oyster|coquillage|shellfish|calmar|squid|poulpe|octopus)\b",
    "is_egg": r"\b(oeuf|œuf|egg)\b",
    "is_dairy": r"\b(lait|milk|fromage|cheese|yaourt|yogurt|yoghurt|crème|cream|beurre|butter|lactose|dairy)\b",
    # Food types - Vegetables
    "is_vegetable": r"\b(légume|legume|vegetable|carotte|carrot|tomate|tomato|courgette|zucchini|aubergine|eggplant|poivron|pepper|oignon|onion|ail|garlic|pomme.{0,3}terre|potato|haricot|bean|petit.{0,3}pois|pea|épinard|spinach|salade|salad|laitue|lettuce|chou|cabbage|brocoli|broccoli|céleri|celery|concombre|cucumber|radis|radish|navet|turnip|betterave|beet|artichaut|artichoke|asperge|asparagus|fenouil|fennel|poireau|leek)\b",
    "is_fruit": r"\b(fruit|pomme|apple|poire|pear|orange|citron|lemon|banane|banana|fraise|strawberry|framboise|raspberry|cerise|cherry|pêche|peche|peach|abricot|apricot|prune|plum|raisin|grape|melon|pastèque|watermelon|mangue|mango|ananas|pineapple|kiwi|figue|fig|datte|date|grenade|pomegranate|papaye|papaya|litchi|lychee|avocat|avocado)\b",
    "is_grain": r"\b(céréale|cereale|cereal|grain|blé|ble|wheat|riz|rice|maïs|mais|corn|orge|barley|avoine|oat|seigle|rye|épeautre|epeautre|spelt|sarrasin|buckwheat|quinoa|millet|sorgho|sorghum|farine|flour|semoule|semolina|pâte|pate|pasta)\b",
    "is_legume": r"\b(légumineuse|legumineuse|legume|légume.{0,3}sec|lentille|lentil|pois|pea|haricot.{0,3}sec|dried.{0,3}bean|fève|feve|fava|pois.{0,3}chiche|chickpea|soja|soy|lupin)\b",
    "is_nut_seed": r"\b(noix|nut|walnut|amande|almond|noisette|hazelnut|pistache|pistachio|cacahuète|cacahuete|peanut|cajou|cashew|pécan|pecan|macadamia|graine|seed|tournesol|sunflower|sésame|sesame|lin|flax|chia|courge|pumpkin|chanvre|hemp|pignon|pine.{0,3}nut)\b",
    "is_oil_fat": r"\b(huile|oil|graisse|fat|margarine|olive|colza|rapeseed|tournesol|sunflower|arachide|peanut|palme|palm|coco|coconut|noix|walnut|sésame|sesame)\b",
    "is_spice": r"\b(épice|epice|spice|herbe|herb|aromate|poivre|pepper|sel|salt|sucre|sugar|cannelle|cinnamon|curcuma|turmeric|gingembre|ginger|paprika|curry|cumin|coriandre|coriander|basilic|basil|thym|thyme|romarin|rosemary|persil|parsley|menthe|mint|aneth|dill|origan|oregano|laurier|bay|muscade|nutmeg|clou.{0,3}girofle|clove|safran|saffron|vanille|vanilla)\b",
    "is_beverage": r"\b(boisson|beverage|drink|jus|juice|café|cafe|coffee|thé|the|tea|vin|wine|bière|biere|beer|alcool|alcohol|eau|water|soda|limonade|lemonade)\b",
    "is_sugar_sweet": r"\b(sucre|sugar|miel|honey|sirop|syrup|confiture|jam|chocolat|chocolate|bonbon|candy|gâteau|gateau|cake|biscuit|cookie|dessert|pâtisserie|patisserie|pastry)\b",
    # LCA process info
    "at_farm_gate": r"\bat\s+(farm\s+)?gate\b",
    "at_plant": r"\bat\s+plant\b",
    "at_processing": r"\bat\s+processing\b",
    "is_greenhouse": r"\b(greenhouse|serre)\b",
    "is_heated_greenhouse": r"\b(heated\s+greenhouse|serre\s+chauffée|serre\s+chauffee)\b",
}

# Index of binary features in the vector
BINARY_FEATURE_NAMES = list(DETECTION_PATTERNS.keys())

# FoodOn feature dimension (loaded from foodon_loader)
FOODON_DIM = 20

# Scale factors to balance FoodOn and regex features

# FoodOn features are already normalized, so scale = 1.0
FOODON_SCALE = 1.0
# Regex features are scaled to have similar magnitude
REGEX_SCALE = math.sqrt(FOODON_DIM / len(DETECTION_PATTERNS))  # ~0.9


def _extract_location(activity_name: str) -> Optional[str]:
    """Extract location code from LCA process name."""
    # Pattern: {FR}, {RoW}, {GLO}, etc.
    match = re.search(r"\{([A-Z]{2,3})\}", activity_name)
    if match:
        return match.group(1)

    # Pattern alternatif: /FR U, /IT U, etc.
    match = re.search(r"/([A-Z]{2})\s*U\b", activity_name)
    if match:
        return match.group(1)

    return None


def _extract_origin(activity_name: str) -> str:
    """Extract origin from the activity name."""
    location = _extract_location(activity_name)
    if location:
        return ORIGIN_MAPPING.get(location, "OutOfEuropeAndMaghreb")

    # Patterns textuels
    activity_lower = activity_name.lower()
    if "by plane" in activity_lower or "by air" in activity_lower:
        return "OutOfEuropeAndMaghrebByPlane"
    if any(x in activity_lower for x in ["france", "french"]):
        return "France"
    if any(
        x in activity_lower for x in ["europe", "eu ", "italian", "spanish", "german"]
    ):
        return "EuropeAndMaghreb"

    return "OutOfEuropeAndMaghreb"


def extract_features(
    name: str, activity_name: str, translate_fn=None, foodon_extractor=None
) -> np.ndarray:
    """
    Extract feature vector combining FoodOn ontology + regex pattern features.

    Features vector structure:
    - [0:20] FoodOn ontology features (scaled)
    - [20:45] Regex binary features (scaled)

    Args:
        name: Ingredient name (potentially French)
        activity_name: Activity/process name
        translate_fn: Optional function to translate name before encoding
        foodon_extractor: Optional FoodOnFeatureExtractor for ontology features

    Returns:
        np.ndarray of dimension (20 + nb_patterns) = 45 dims
    """
    # Combine name + activity for regex matching
    full_text = f"{name} {activity_name}".lower()

    # 1. FoodOn features (20 dims) - uses translated name for English ontology
    if foodon_extractor is not None:
        # Translate name for FoodOn (English-based ontology)
        name_for_foodon = translate_fn(name) if translate_fn else name
        foodon_features = foodon_extractor.extract_features(name_for_foodon)
    else:
        foodon_features = np.zeros(FOODON_DIM, dtype=np.float32)
    foodon_scaled = foodon_features * FOODON_SCALE

    # 2. Regex binary features (25 dims) - scaled for equal weight
    binary_features = []
    for pattern_name, pattern in DETECTION_PATTERNS.items():
        match = 1.0 if re.search(pattern, full_text, re.IGNORECASE) else 0.0
        binary_features.append(match)
    regex_features = np.array(binary_features, dtype=np.float32) * REGEX_SCALE

    # Concatenate features
    return np.concatenate([foodon_scaled, regex_features])


# =============================================================================
# PREDICTOR CLASS
# =============================================================================


class Predictor:
    """
    Metadata predictor for food ingredients.

    Uses FoodOn ontology + regex pattern features for nearest neighbor matching.
    Combines:
    - Nearest neighbor matching for foodType, processingState, cropGroup, transportCooling
    - Nearest neighbor matching for density, inediblePart, rawToCookedRatio
    - Rule-based extraction for defaultOrigin
    """

    def __init__(self):
        """Initialize predictor."""
        # SentenceTransformer for evaluation cross-validation only
        self.model = None
        self._model_loaded = False

        # Translation model (FR → EN)
        self.mt_tokenizer = None
        self.mt_model = None
        self.device = "cuda" if torch.cuda.is_available() else "cpu"
        self._translation_cache = (
            self._load_translation_cache()
        )  # Load from disk if exists

        # FoodOn feature extractor (lazy loaded)
        self.foodon_extractor = None
        self._foodon_loaded = False

        # Matchers for categorical metadata (nearest neighbor approach)
        self.food_type_matcher = None
        self.processing_matcher = None
        self.transport_matcher = None

        # CropGroup matcher (nearest neighbor)
        self.cropgroup_matcher = None

        # Value matchers for continuous values (nearest neighbor on reference data)
        self.density_matcher = None
        self.inedible_matcher = None
        self.ratio_matcher = None

        # Training data (for evaluation)
        self.training_features = None
        self.training_ingredients = None

        # Metadata
        self.is_fitted = False
        self.feature_dim = None

    @staticmethod
    def _load_translation_cache() -> dict:
        """Load translation cache from disk if exists."""
        if TRANSLATION_CACHE_PATH.exists():
            try:
                with open(TRANSLATION_CACHE_PATH, "rb") as f:
                    cache = pickle.load(f)
                print(f"Loaded {len(cache)} cached translations from disk")
                return cache
            except Exception:
                return {}
        return {}

    def _save_translation_cache(self):
        """Save translation cache to disk."""
        with open(TRANSLATION_CACHE_PATH, "wb") as f:
            pickle.dump(self._translation_cache, f)
        print(f"Saved {len(self._translation_cache)} translations to cache")

    @staticmethod
    def clear_translation_cache():
        """Clear the translation cache file."""
        if TRANSLATION_CACHE_PATH.exists():
            TRANSLATION_CACHE_PATH.unlink()
            print("Translation cache cleared")

    def _load_translation_model(self):
        """Load translation model (lazy loading)."""
        if self.mt_model is None:
            print(f"Loading translation model: {MT_MODEL}")
            self.mt_tokenizer = AutoTokenizer.from_pretrained(MT_MODEL)
            self.mt_model = AutoModelForSeq2SeqLM.from_pretrained(MT_MODEL).to(
                self.device
            )

    def _load_embedding_model(self):
        """Load embedding model for evaluation only (lazy loading)."""
        if not self._model_loaded:
            print("Importing sentence_transformers...")
            from sentence_transformers import SentenceTransformer

            print(f"Loading embedding model: {MODEL}")
            self.model = SentenceTransformer(MODEL)
            self._model_loaded = True

    def _load_foodon(self):
        """Load FoodOn feature extractor (lazy loading)."""
        if not self._foodon_loaded:
            from foodon_loader import FoodOnFeatureExtractor

            self.foodon_extractor = FoodOnFeatureExtractor()
            self._foodon_loaded = True

    def _translate(self, text: str) -> str:
        """Translate French text to English (with caching)."""
        # Clean up noise words (country codes, "par défaut", etc.) before translation
        text = cleanup_name(text)
        if not text:
            return ""

        # Check cache first
        if text in self._translation_cache:
            return self._translation_cache[text]

        inputs = self.mt_tokenizer(text, return_tensors="pt").to(self.device)
        with torch.no_grad():
            outputs = self.mt_model.generate(**inputs, max_length=40)
        result = self.mt_tokenizer.batch_decode(outputs, skip_special_tokens=True)[
            0
        ].strip()

        # Cache the result
        self._translation_cache[text] = result
        return result

    def _get_base_category(self, categories: list) -> str:
        """Extract base category (not organic/bleublanccoeur)."""
        for cat in categories:
            if cat in BASE_CATEGORIES:
                return cat
        return "misc"

    def _get_additive_labels(self, categories: list) -> list:
        """Extract additive labels."""
        return [cat for cat in categories if cat in ADDITIVE_LABELS]

    def _is_vegetal(self, categories: list) -> bool:
        """Determine if ingredient is vegetal (requires cropGroup)."""
        vegetal_categories = {
            "vegetable_fresh",
            "vegetable_processed",
            "grain_raw",
            "grain_processed",
            "nut_oilseed_raw",
            "nut_oilseed_processed",
            "spice_condiment_additive",
        }
        return any(cat in vegetal_categories for cat in categories)

    def _extract_binary_from_features(self, features: np.ndarray) -> dict:
        """Extract binary regex features from the feature vector."""
        # Features: [0:20] FoodOn, [20:45] regex
        regex_start = FOODON_DIM  # 20
        binary_values = features[0, regex_start:]  # Skip FoodOn to get regex features
        # Unscale to get original binary values
        binary_values = binary_values / REGEX_SCALE
        return {
            name: bool(binary_values[i] > 0.5)
            for i, name in enumerate(BINARY_FEATURE_NAMES)
        }

    def _predict_category_by_rules(self, binary_features: dict) -> str | None:
        """Apply deterministic rules for category. Returns None if no rule matches."""
        if binary_features.get("is_fish") or binary_features.get("is_seafood"):
            return "animal_product"
        if binary_features.get("is_meat"):
            return "animal_product"
        if binary_features.get("is_egg"):
            return "animal_product"
        if binary_features.get("is_dairy"):
            return "dairy_product"
        return None

    def _predict_transport_by_rules(self, binary_features: dict) -> str | None:
        """Apply deterministic rules for transportCooling. Returns None if no rule matches."""
        if binary_features.get("is_frozen"):
            return "always"
        if binary_features.get("is_fresh") and (
            binary_features.get("is_fish")
            or binary_features.get("is_seafood")
            or binary_features.get("is_meat")
            or binary_features.get("is_dairy")
        ):
            return "always"
        return None

    def _detect_packaging(self, text: str) -> tuple[str | None, str | None]:
        """
        Detect packaging type from text and return (packaging, transportCooling).

        Returns:
            (packaging_type, transport_cooling) or (None, None) if not detected
        """
        text_lower = text.lower()
        for pkg_type, (pattern, transport) in PACKAGING_PATTERNS.items():
            if re.search(pattern, text_lower, re.IGNORECASE):
                return pkg_type, transport
        return None, None

    def _get_transport_from_packaging(
        self, packaging: str | None, food_type: str
    ) -> str:
        """
        Determine transportCooling from packaging and foodType.

        If packaging is 'fresh' or None, uses foodType to decide:
        - meat, fish_seafood, dairy, vegetable, fruit → always
        - grain, nut_oilseed, spice_condiment, misc → none
        """
        if packaging and packaging != "fresh":
            # Packaging has a direct mapping
            _, transport = PACKAGING_PATTERNS.get(packaging, (None, None))
            if transport:
                return transport

        # Fresh or unknown packaging: use foodType
        perishable_types = {"meat", "fish_seafood", "dairy", "vegetable", "fruit"}
        if food_type in perishable_types:
            return "always"
        return "none"

    def _build_matcher(
        self, names: list, values: list, sources: list
    ) -> NearestNeighborMatcher:
        """Build a NearestNeighborMatcher with common configuration."""
        return NearestNeighborMatcher(
            names,
            values,
            sources=sources,
            translate_fn=self._translate,
            foodon_extractor=self.foodon_extractor,
        )

    def fit(self, ingredients: list[dict], verbose: bool = True):
        """
        Train the predictor on a list of ingredients.

        Args:
            ingredients: List of dicts with at least "name" and "activityName"
        """

        def timed_print(msg, start_time=[None]):
            if start_time[0] is not None:
                elapsed = time.time() - start_time[0]
                print(f"  [{elapsed:.1f}s]")
            print(msg, end="", flush=True)
            start_time[0] = time.time()

        self._load_translation_model()
        self._load_foodon()

        if verbose:
            timed_print(f"Training on {len(ingredients)} ingredients...\n")

        # 1. Pre-translate all ingredient names (batch for performance)
        cache_size_before = len(self._translation_cache)
        if verbose:
            timed_print(f"Translating ingredient names ({cache_size_before} cached)...")
        translated_names = [self._translate(ing.get("name", "")) for ing in ingredients]
        cache_hits = cache_size_before
        cache_misses = len(self._translation_cache) - cache_size_before
        if verbose and cache_misses > 0:
            print(f" ({cache_hits} hits, {cache_misses} new)", end="")

        # 2. Extract features for all ingredients
        if verbose:
            timed_print("Extracting features...")

        features_list = []
        for i, ing in enumerate(ingredients):
            activity = ing.get("activityName", "")
            feat = extract_features(
                translated_names[i],
                activity,
                translate_fn=None,  # Already translated
                foodon_extractor=self.foodon_extractor,
            )
            features_list.append(feat)

        self.training_features = np.array(features_list)
        self.training_ingredients = ingredients
        self.feature_dim = self.training_features.shape[1]

        # 3. Build foodType matcher (nearest neighbor)
        # Use ONLY reference data from food_type.csv - NOT ingredients.json
        if verbose:
            timed_print("Building foodType matcher...")

        ref_food_names, ref_food_types, ref_food_sources = _load_food_type_data()

        self.food_type_matcher = self._build_matcher(
            ref_food_names, ref_food_types, ref_food_sources
        )

        # 3b. Build processingState matcher (nearest neighbor)
        if verbose:
            timed_print("Building processingState matcher...")

        # Extract processingState from training ingredients
        ing_names_proc = [ing["name"] for ing in ingredients]
        y_processing = []
        proc_sources = []
        for ing in ingredients:
            base_cat = self._get_base_category(ing.get("categories", ["misc"]))
            _, proc_state = CATEGORY_TO_DIMENSIONS.get(base_cat, ("misc", "processed"))
            y_processing.append(proc_state)
            proc_sources.append("ingredients.json")

        # Add reference data from processing_state.csv
        ref_proc_names, ref_proc_states, ref_proc_sources = (
            _load_processing_state_data()
        )
        ing_names_proc.extend(ref_proc_names)
        y_processing.extend(ref_proc_states)
        proc_sources.extend(ref_proc_sources)

        self.processing_matcher = self._build_matcher(
            ing_names_proc, y_processing, proc_sources
        )

        # 4. Build cropGroup matcher (nearest neighbor)
        if verbose:
            timed_print("Building cropGroup matcher...")

        # Start with reference data from cropgroup.csv
        cropgroup_names, cropgroup_vals, cropgroup_sources = _load_cropgroup_data()

        # Add training data from ingredients with cropGroup
        ing_cg_names, ing_cg_vals, ing_cg_sources = _build_cropgroup_data(ingredients)
        cropgroup_names.extend(ing_cg_names)
        cropgroup_vals.extend(ing_cg_vals)
        cropgroup_sources.extend(ing_cg_sources)

        if cropgroup_names:
            self.cropgroup_matcher = self._build_matcher(
                cropgroup_names, cropgroup_vals, cropgroup_sources
            )

        # 5. Build transportCooling matcher (combines ingredients.json + reference data)
        if verbose:
            timed_print("Building transportCooling matcher...")

        transport_names = [ing["name"] for ing in ingredients]
        y_transport = [ing.get("transportCooling", "none") for ing in ingredients]
        transport_sources = ["ingredients.json"] * len(ingredients)

        ref_transport_names, ref_transport, ref_transport_sources = (
            _load_transport_data()
        )
        transport_names.extend(ref_transport_names)
        y_transport.extend(ref_transport)
        transport_sources.extend(ref_transport_sources)

        self.transport_matcher = self._build_matcher(
            transport_names, y_transport, transport_sources
        )

        # 6. Build nearest neighbor matchers for continuous values
        # Each matcher combines ingredients.json + reference CSV data

        def build_value_matcher(field, ref_loader, allow_zero=False, name=None):
            """Helper to build a matcher combining ingredients + reference data."""
            if verbose:
                timed_print(f"Building {name or field} matcher...")
            names, vals, sources = _extract_ingredient_values(
                ingredients, field, allow_zero=allow_zero
            )
            ref_names, ref_vals, ref_sources = ref_loader()
            names.extend(ref_names)
            vals.extend(ref_vals)
            sources.extend(ref_sources)
            return self._build_matcher(names, vals, sources)

        self.density_matcher = build_value_matcher(
            "ingredientDensity", _load_density_data, name="density"
        )
        self.inedible_matcher = build_value_matcher(
            "inediblePart", _load_inedible_data, allow_zero=True, name="inedible part"
        )
        self.ratio_matcher = build_value_matcher(
            "rawToCookedRatio", _load_ratio_data, name="raw-to-cooked ratio"
        )

        self.is_fitted = True

        # Save translation cache to disk for faster subsequent runs
        self._save_translation_cache()

        if verbose:
            timed_print("✓ Training complete!\n")

    def _get_foodtype_from_foodon_features(self, features: np.ndarray) -> str | None:
        """
        Get food type directly from FoodOn features (indices 0-8).
        Returns None if no clear FoodOn signal.

        Features layout (from foodon_loader.py):
        - [0]=vegetable, [1]=fruit, [2]=grain, [3]=meat(placeholder),
        - [4]=fish, [5]=dairy, [6]=nut_oilseed, [7]=spice, [8]=beverage
        - [19]=match_confidence
        """
        # Check confidence threshold (FoodOn match confidence is at features[19])
        foodon_confidence = features[19] if len(features) > 19 else 0
        if foodon_confidence < 0.7:  # Require decent FoodOn match
            return None

        # Check in priority order: more specific types first
        # (fruit before vegetable, since fruits are a subtype of plant food in FoodOn)
        priority_order = [
            (1, "fruit"),         # Check fruit BEFORE vegetable
            (2, "grain"),
            (4, "fish_seafood"),
            (5, "dairy"),
            (6, "nut_oilseed"),
            (7, "spice_condiment"),
            (8, "beverage"),
            (0, "vegetable"),     # Check vegetable LAST (it's the most generic plant category)
        ]

        for idx, food_type in priority_order:
            if features[idx] > 0.5:  # Feature is active
                return food_type

        return None

    def predict(self, ingredient: dict) -> dict:
        """
        Predict metadata for a new ingredient.

        Args:
            ingredient: Dict with "name" and optionally "activityName"

        Returns:
            Dict with predicted values and match info (including confidence)
        """
        if not self.is_fitted:
            raise RuntimeError(
                "Predictor must be fitted before prediction. Call fit() first."
            )

        self._load_translation_model()
        self._load_foodon()

        name = ingredient.get("name", "")
        activity = ingredient.get("activityName", "")
        full_text = f"{name} {activity}"

        # Extract features (with translation and FoodOn)
        features = extract_features(
            name,
            activity,
            translate_fn=self._translate,
            foodon_extractor=self.foodon_extractor,
        ).reshape(1, -1)

        predictions = {}

        # Extract binary features for rules
        binary_features = self._extract_binary_from_features(features)

        def _match(file: str, name: str, conf: float) -> dict:
            """Build match info dict with confidence."""
            return {"file": file, "name": name, "confidence": round(conf, 3)}

        # 1. FoodType - Check food_type.csv exact match FIRST, then FoodOn, then fallback
        food_type, conf, match, source = self.food_type_matcher.predict(
            name, translate_fn=self._translate
        )
        if conf == 1.0:  # Only trust exact match from food_type.csv (cosine can be 0.95+)
            predictions["foodTypeMatch"] = _match(source, match, conf)
        else:
            # Try FoodOn features
            foodon_type = self._get_foodtype_from_foodon_features(features.flatten())
            if foodon_type:
                food_type = foodon_type
                predictions["foodTypeMatch"] = _match("FoodOn", "ontology", 1.0)
            else:
                # Keep the matcher result (cosine similarity fallback)
                predictions["foodTypeMatch"] = _match(source, match, conf)
        predictions["foodType"] = food_type

        # 2. ProcessingState (packaging detection first, then nearest neighbor)
        packaging, _ = self._detect_packaging(full_text)
        if packaging and packaging != "fresh":
            processing_state = "processed"
            predictions["processingStateMatch"] = None
        else:
            processing_state, conf, match, source = self.processing_matcher.predict(
                name, translate_fn=self._translate
            )
            predictions["processingStateMatch"] = _match(source, match, conf)
        predictions["processingState"] = processing_state
        predictions["packaging"] = packaging

        # 3. Additive labels (by rules)
        labels = []
        if re.search(r"\b(bio|organic)\b", full_text, re.IGNORECASE):
            labels.append("organic")
        if re.search(r"\b(bleu.?blanc.?c[oœ]eur)\b", full_text, re.IGNORECASE):
            labels.append("bleublanccoeur")
        predictions["labels"] = labels

        # 4. Build categories from foodType + processingState + labels
        base_category = DIMENSIONS_TO_CATEGORY.get(
            (food_type, processing_state), "misc"
        )
        predictions["categories"] = [base_category] + labels

        # 5. cropGroup (for vegetal types) - nearest neighbor matching
        vegetal_types = {
            "vegetable",
            "fruit",
            "grain",
            "nut_oilseed",
            "spice_condiment",
        }
        if food_type in vegetal_types and self.cropgroup_matcher is not None:
            cropgroup_val, conf, match, source = self.cropgroup_matcher.predict(
                name, translate_fn=self._translate
            )
            predictions["cropGroup"] = cropgroup_val
            predictions["cropGroupMatch"] = _match(source, match, conf)
        else:
            predictions["cropGroup"] = None
            predictions["cropGroupMatch"] = None

        # 6. transportCooling (packaging first, then rules, then nearest neighbor)
        if packaging and packaging != "fresh":
            _, transport_cooling = PACKAGING_PATTERNS.get(packaging, (None, None))
            transport_cooling = transport_cooling or "none"
            predictions["transportCoolingMatch"] = None
        else:
            transport_cooling = self._predict_transport_by_rules(binary_features)
            if transport_cooling:
                predictions["transportCoolingMatch"] = None
            else:
                transport_cooling, conf, match, source = self.transport_matcher.predict(
                    name, translate_fn=self._translate
                )
                predictions["transportCoolingMatch"] = _match(source, match, conf)
        predictions["transportCooling"] = transport_cooling

        # 7. defaultOrigin (by rules)
        predictions["defaultOrigin"] = _extract_origin(activity)

        # 8. Continuous values (nearest neighbor)
        density_val, conf, match, source = self.density_matcher.predict(
            name, translate_fn=self._translate
        )
        predictions["density"] = round(density_val, 3)
        predictions["densityMatch"] = _match(source, match, conf)

        inedible_val, conf, match, source = self.inedible_matcher.predict(
            name, translate_fn=self._translate
        )
        predictions["inediblePart"] = round(inedible_val, 2)
        predictions["inediblePartMatch"] = _match(source, match, conf)

        ratio_val, conf, match, source = self.ratio_matcher.predict(
            name, translate_fn=self._translate
        )
        predictions["rawToCookedRatio"] = round(ratio_val, 3)
        predictions["rawToCookedRatioMatch"] = _match(source, match, conf)

        return predictions

    def evaluate(self, verbose: bool = True) -> dict:
        """
        Evaluate predictor with cross-validation on training data.

        Returns:
            Dict with scores per metadata field
        """
        if not self.is_fitted:
            raise RuntimeError("Predictor must be fitted before evaluation.")

        def _cv_score(y_values: list, field_name: str, X=None, cv=5) -> dict:
            """Run cross-validation and return {mean, std}."""
            features = X if X is not None else self.training_features
            encoder = LabelEncoder()
            y_encoded = encoder.fit_transform(y_values)
            cv_scores = cross_val_score(
                RandomForestClassifier(
                    n_estimators=100, class_weight="balanced", random_state=42
                ),
                features,
                y_encoded,
                cv=cv,
                scoring="accuracy",
            )
            if verbose:
                print(
                    f"{field_name} accuracy: {cv_scores.mean():.3f} ± {cv_scores.std():.3f}"
                )
            return {"mean": cv_scores.mean(), "std": cv_scores.std()}

        scores = {}

        # Extract foodType and processingState from categories
        y_food = []
        y_proc = []
        for ing in self.training_ingredients:
            base_cat = self._get_base_category(ing.get("categories", ["misc"]))
            food_type, proc_state = CATEGORY_TO_DIMENSIONS.get(
                base_cat, ("misc", "processed")
            )
            y_food.append(food_type)
            y_proc.append(proc_state)

        scores["foodType"] = _cv_score(y_food, "FoodType")
        scores["processingState"] = _cv_score(y_proc, "ProcessingState")
        scores["transportCooling"] = _cv_score(
            [ing.get("transportCooling", "none") for ing in self.training_ingredients],
            "TransportCooling",
        )

        # Evaluate cropGroup (vegetables only, using RandomForest on embeddings)
        cropgroup_names, cropgroup_vals, _ = _build_cropgroup_data(
            self.training_ingredients
        )
        if len(cropgroup_names) > 10:
            self._load_embedding_model()
            X_crop = self.model.encode(cropgroup_names)
            scores["cropGroup"] = _cv_score(
                cropgroup_vals,
                "CropGroup",
                X=X_crop,
                cv=min(5, len(set(cropgroup_vals))),
            )

        return scores

    def save(self, path: str):
        """Save the trained predictor."""
        if not self.is_fitted:
            raise RuntimeError("Cannot save unfitted predictor.")

        # Clear unpicklable references from matchers
        matchers = [
            self.food_type_matcher,
            self.processing_matcher,
            self.transport_matcher,
            self.cropgroup_matcher,
            self.density_matcher,
            self.inedible_matcher,
            self.ratio_matcher,
        ]
        for matcher in matchers:
            if matcher is not None:
                matcher.foodon_extractor = None
                matcher.translate_fn = None  # Can't pickle bound methods

        # Don't save embedding model or FoodOn (reloaded lazily)
        state = {
            # Categorical matchers (nearest neighbor approach)
            "food_type_matcher": self.food_type_matcher,
            "processing_matcher": self.processing_matcher,
            "transport_matcher": self.transport_matcher,
            # CropGroup matcher (nearest neighbor)
            "cropgroup_matcher": self.cropgroup_matcher,
            # Value matchers (nearest neighbor on reference data)
            "density_matcher": self.density_matcher,
            "inedible_matcher": self.inedible_matcher,
            "ratio_matcher": self.ratio_matcher,
            # Translation cache (avoid re-translating on reload)
            "_translation_cache": self._translation_cache,
            # Training data (for evaluation)
            "training_features": self.training_features,
            "training_ingredients": self.training_ingredients,
            "feature_dim": self.feature_dim,
            "is_fitted": True,
            # FoodOn state (extractor is reloaded lazily)
            "_foodon_loaded": False,
        }

        with open(path, "wb") as f:
            pickle.dump(state, f)

        print(f"✓ Predictor saved to {path}")

    @classmethod
    def load(cls, path: str) -> "Predictor":
        """Load a saved predictor."""
        predictor = cls()

        with open(path, "rb") as f:
            state = pickle.load(f)

        for key, value in state.items():
            setattr(predictor, key, value)

        print(f"✓ Predictor loaded from {path}")
        return predictor


# =============================================================================
# INTEGRATION with ecobalyse_data/detect
# =============================================================================

# For compatibility with existing pattern
THRESHOLD = 0.6
SCORE_KEY = "predict_Score"
MATCH_KEY = "predict_BestMatch"
BAD, GOOD = 0.5, 0.8

_predictor_instance: Optional[Predictor] = None


def _name(obj):
    return obj.get("name", "")


def _get(obj):
    return obj.get("categories")


def _set(obj, predictions):
    """Apply predictions to the object."""
    for key, value in predictions.items():
        if value is not None:
            obj[key] = value


class Detector:
    """Interface compatible with other detectors."""

    def __init__(
        self, model_path: Optional[str] = None, training_data: Optional[list] = None
    ):
        """
        Args:
            model_path: Path to a saved model
            training_data: Training data (if no saved model provided)
        """
        self.predictor = Predictor()

        if model_path and Path(model_path).exists():
            self.predictor = Predictor.load(model_path)
        elif training_data:
            self.predictor.fit(training_data)
        else:
            raise ValueError("Either model_path or training_data must be provided")

    def detect(self, ingredient, debug=False):
        """
        Predict metadata for an ingredient.

        Returns:
            (predictions, score, best_match)
        """
        predictions = self.predictor.predict(ingredient)

        # Extract confidence from match dicts
        def _get_conf(match_key):
            match = predictions.get(match_key)
            return match.get("confidence", 0) if match else 0

        # Score global = moyenne des confiances
        score = np.mean(
            [
                _get_conf("densityMatch"),
                _get_conf("inediblePartMatch"),
                _get_conf("rawToCookedRatioMatch"),
            ]
        )

        best_match = f"density={predictions.get('density')}, inedible={predictions.get('inediblePart')}"

        return predictions, score, best_match


def update(input_json, threshold=THRESHOLD, debug=False, model_path=None):
    """
    Update metadata for all ingredients.

    Compatible with existing CLI.

    Args:
        input_json: List of ingredients
        threshold: Confidence threshold for predictions
        debug: Add debug info to output
        model_path: Path to saved model (optional)
    """
    from rich.progress import track

    # Filter ingredients that already have all metadata
    to_predict = [ing for ing in input_json if not _get(ing)]
    already_done = [ing for ing in input_json if _get(ing)]

    if not to_predict:
        print("All ingredients already have metadata.")
        return input_json

    # Train on existing ingredients if no model provided
    detector = Detector(model_path=model_path, training_data=already_done or input_json)

    output_json = list(already_done)

    print(f"Predicting metadata for {len(to_predict)} ingredients:")
    for ingredient in track(to_predict, description="Predicting"):
        predictions, score, best_match = detector.detect(ingredient, debug)

        if score >= threshold:
            _set(ingredient, predictions)

            if debug:
                ingredient[SCORE_KEY] = score
                ingredient[MATCH_KEY] = best_match

            output_json.append(ingredient)
        else:
            print(
                f"\n⚠️  Low confidence for '{_name(ingredient)}' "
                f"(score: {score:.2f}, best match: '{best_match}')"
            )
            output_json.append(ingredient)

    return output_json


def detect(ingredient, model_path=None, training_data=None):
    """Simple interface to detect a single ingredient."""
    detector = Detector(model_path=model_path, training_data=training_data)
    return detector.detect(ingredient)


# =============================================================================
# CLI
# =============================================================================


def main():
    import argparse

    parser = argparse.ArgumentParser(description="Predict ingredient metadata using ML")
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # Train command
    train_parser = subparsers.add_parser("train", help="Train predictor on ingredients")
    train_parser.add_argument(
        "input", type=str, help="Input JSON file with ingredients"
    )
    train_parser.add_argument(
        "--output", "-o", type=str, default="predictor.pkl", help="Output model file"
    )

    # Infer command
    infer_parser = subparsers.add_parser(
        "infer", help="Predict metadata for new ingredient"
    )
    infer_parser.add_argument("model", type=str, help="Model file (.pkl)")
    infer_parser.add_argument(
        "--name", "-n", type=str, required=True, help="Ingredient name"
    )
    infer_parser.add_argument(
        "--activity", "-a", type=str, required=True, help="Activity/process name"
    )

    # Evaluate command
    eval_parser = subparsers.add_parser(
        "evaluate", help="Evaluate predictor with cross-validation"
    )
    eval_parser.add_argument("input", type=str, help="Input JSON file with ingredients")

    args = parser.parse_args()

    if args.command == "train":
        with open(args.input) as f:
            ingredients = json.load(f)

        predictor = Predictor()
        predictor.fit(ingredients)
        predictor.save(args.output)

    elif args.command == "infer":
        predictor = Predictor.load(args.model)

        ingredient = {
            "name": args.name,
            "activityName": args.activity,
        }

        predictions = predictor.predict(ingredient)

        print("\n📊 Predictions:")
        for key, value in predictions.items():
            if key.endswith("Match"):
                continue  # Skip match info in summary
            match_key = f"{key}Match"
            match = predictions.get(match_key)
            if match and match.get("confidence"):
                print(
                    f"  {key}: {value} (conf: {match['confidence']:.2f}, match: {match['name']})"
                )
            else:
                print(f"  {key}: {value}")

    elif args.command == "evaluate":
        with open(args.input) as f:
            ingredients = json.load(f)

        predictor = Predictor()
        predictor.fit(ingredients)

        print("\n📈 Cross-validation results:")
        predictor.evaluate()

    else:
        parser.print_help()


if __name__ == "__main__":
    main()
