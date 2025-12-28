"""
FoodOn Ontology Feature Extractor
=================================

Extracts structured features from FoodOn ontology for food ingredient classification.
Used to supplement E5 embeddings with explicit food category knowledge.

FoodOn: https://foodon.org/
"""

import warnings
from pathlib import Path

import numpy as np

# Suppress pronto warnings
warnings.filterwarnings("ignore", category=SyntaxWarning)
warnings.filterwarnings("ignore", category=UnicodeWarning)

FOODON_PATH = Path(__file__).parent / "data" / "foodon.owl"
FOODON_URL = "http://purl.obolibrary.org/obo/foodon.owl"


def _download_foodon(destination: Path) -> None:
    """Download FoodOn ontology from OBO Foundry.

    Args:
        destination: Path to save the foodon.owl file
    """
    import urllib.request

    print(f"Downloading FoodOn ontology from {FOODON_URL}...")
    print("(This is a ~200MB file, may take a few minutes)")

    # Ensure data directory exists
    destination.parent.mkdir(parents=True, exist_ok=True)

    # Download with progress indication
    urllib.request.urlretrieve(FOODON_URL, destination)
    print(f"FoodOn downloaded to {destination}")


# FoodOn term IDs for food categories (verified via pronto)
FOODON_CATEGORIES = {
    "vegetable": "FOODON:00001261",  # vegetable food product
    "fruit": "FOODON:00001057",  # plant fruit food product (apples, pears, berries, etc.)
    "grain": "FOODON:00001093",  # cereal grain food product
    "fish_seafood": "FOODON:00001248",  # fish food product
    "dairy": "FOODON:00001256",  # dairy food product
    "nut_oilseed": "FOODON:00001172",  # nut food product
    "spice": "FOODON:03303380",  # spice food product
    "beverage": "FOODON:03301977",  # beverage food product
    "plant": "FOODON:00001015",  # plant food product (parent of veg/fruit)
}

# Number of features extracted
FOODON_FEATURE_DIM = 20


class FoodOnFeatureExtractor:
    """Extract structured features from FoodOn ontology."""

    def __init__(self, foodon_path: Path = FOODON_PATH):
        """
        Load FoodOn ontology and build lookup indices.

        Downloads foodon.owl automatically if it doesn't exist.

        Args:
            foodon_path: Path to foodon.owl file
        """
        import pronto

        # Download FoodOn if not present
        if not foodon_path.exists():
            _download_foodon(foodon_path)

        print("Loading FoodOn ontology...")
        self.ontology = pronto.Ontology(str(foodon_path))
        self._build_indices()
        print(f"FoodOn loaded: {len(self.label_to_term)} terms indexed")

    def _build_indices(self):
        """Build lookup indices for fast matching.

        Prioritizes FOODON terms over NCBITaxon (organism) terms.
        """
        self.label_to_term = {}
        self.food_product_terms = {}  # Separate index for food product terms

        for term in self.ontology.terms():
            if not term.name:
                continue

            label = term.name.lower()
            is_food_term = term.id.startswith("FOODON:")

            # Always index food terms, only index non-food if no collision
            if is_food_term:
                self.label_to_term[label] = term
                self.food_product_terms[label] = term
            elif label not in self.label_to_term:
                self.label_to_term[label] = term

            # Index by synonyms (prefer food terms)
            for syn in getattr(term, "synonyms", []):
                if hasattr(syn, "description") and syn.description:
                    syn_label = syn.description.lower()
                    if is_food_term:
                        self.label_to_term[syn_label] = term
                        self.food_product_terms[syn_label] = term
                    elif syn_label not in self.label_to_term:
                        self.label_to_term[syn_label] = term

    def lookup(self, name: str, threshold: float = 0.6):
        """
        Match ingredient name to FoodOn food product term.

        Prioritizes FOODON: terms (food products) over NCBITaxon (organisms).
        Uses fast dictionary lookups instead of slow fuzzy matching.

        Args:
            name: Ingredient name to look up
            threshold: Minimum similarity score (not used, kept for compatibility)

        Returns:
            (term, confidence) - term is None if no match found
        """
        name_lower = name.lower().strip()

        # Skip very short names (noise)
        if len(name_lower) < 3:
            return None, 0.0

        # 1. Exact match in food product terms first (highest priority)
        if name_lower in self.food_product_terms:
            return self.food_product_terms[name_lower], 1.0

        # 2. Try adding "food product" suffix
        food_product_key = f"{name_lower} food product"
        if food_product_key in self.food_product_terms:
            return self.food_product_terms[food_product_key], 0.95

        # 3. Try adding "vegetable food product" suffix
        veg_key = f"{name_lower} vegetable food product"
        if veg_key in self.food_product_terms:
            return self.food_product_terms[veg_key], 0.95

        # 4. Try adding "fruit food product" suffix
        fruit_key = f"{name_lower} fruit food product"
        if fruit_key in self.food_product_terms:
            return self.food_product_terms[fruit_key], 0.95

        # Extract main words from name (skip common words)
        skip_words = {
            "de",
            "le",
            "la",
            "les",
            "du",
            "des",
            "en",
            "au",
            "aux",
            "et",
            "ou",
            "bio",
            "fr",
            "organic",
            "in",
            "shell",
            "with",
            "without",
        }
        words = [
            w
            for w in name_lower.replace(",", " ").split()
            if w not in skip_words and len(w) >= 3
        ]

        # 5. Try each significant word with various suffixes
        for word in words:
            # Try singular form (remove trailing 's')
            singular = (
                word.rstrip("s") if word.endswith("s") and len(word) > 4 else word
            )

            # Try "(raw)" suffix first (common in FoodOn)
            for base in [singular, word]:
                raw_key = f"{base} (raw)"
                if raw_key in self.food_product_terms:
                    return self.food_product_terms[raw_key], 0.95

            # Word as nut food product
            for base in [singular, word]:
                word_nut = f"{base} nut food product"
                if word_nut in self.food_product_terms:
                    return self.food_product_terms[word_nut], 0.9

            # Word as vegetable food product
            for base in [singular, word]:
                word_veg = f"{base} vegetable food product"
                if word_veg in self.food_product_terms:
                    return self.food_product_terms[word_veg], 0.9

            # Word as food product
            for base in [singular, word]:
                word_food = f"{base} food product"
                if word_food in self.food_product_terms:
                    return self.food_product_terms[word_food], 0.85

            # Exact word match in food_product_terms
            for base in [singular, word]:
                if base in self.food_product_terms:
                    term = self.food_product_terms[base]
                    # Skip obsolete terms
                    if "obsolete" not in (term.name or "").lower():
                        return term, 0.85

            # Word in food product label (substring match) - be more selective
            for base in [singular, word]:
                for label, term in self.food_product_terms.items():
                    # Skip obsolete terms and require the word to be at the start
                    if "obsolete" in label:
                        continue
                    if label.startswith(base) and "food product" in label:
                        return term, 0.8

        # 6. Fallback to general label_to_term (may include non-food terms)
        if name_lower in self.label_to_term:
            term = self.label_to_term[name_lower]
            # Only use if it's a FOODON term
            if term.id.startswith("FOODON:"):
                return term, 0.7

        # No match found
        return None, 0.0

    def extract_features(self, name: str) -> np.ndarray:
        """
        Extract FoodOn feature vector for ingredient name.

        Features (20 dimensions):
        - 0-8: Binary type features (vegetable, fruit, grain, meat, fish, dairy, nut, spice, beverage)
        - 9-13: Processing features (raw, cooked, preserved, fermented, processed)
        - 14-17: Source features (plant, animal, fungus, mineral)
        - 18-19: Numeric features (hierarchy_depth, match_confidence)

        Args:
            name: Ingredient name

        Returns:
            Feature vector of shape (20,)
        """
        term, confidence = self.lookup(name)

        # Initialize feature vector (20 dims)
        features = np.zeros(FOODON_FEATURE_DIM, dtype=np.float32)

        if term is None:
            # No FoodOn match - return zeros (will rely on E5/regex)
            return features

        # Get all ancestor IDs
        ancestors = set(a.id for a in term.superclasses())

        # Binary type features (0-8)
        features[0] = 1.0 if FOODON_CATEGORIES["vegetable"] in ancestors else 0.0
        features[1] = 1.0 if FOODON_CATEGORIES["fruit"] in ancestors else 0.0
        features[2] = 1.0 if FOODON_CATEGORIES["grain"] in ancestors else 0.0
        # Note: meat is detected via animal source feature below
        features[3] = 0.0  # is_meat (placeholder - FoodOn structure varies)
        features[4] = 1.0 if FOODON_CATEGORIES["fish_seafood"] in ancestors else 0.0
        features[5] = 1.0 if FOODON_CATEGORIES["dairy"] in ancestors else 0.0
        features[6] = 1.0 if FOODON_CATEGORIES["nut_oilseed"] in ancestors else 0.0
        features[7] = 1.0 if FOODON_CATEGORIES["spice"] in ancestors else 0.0
        features[8] = 1.0 if FOODON_CATEGORIES["beverage"] in ancestors else 0.0

        # Processing features (9-13) - detect from term name
        term_name_lower = (term.name or "").lower()
        features[9] = 1.0 if "raw" in term_name_lower else 0.0  # is_raw
        features[10] = (
            1.0
            if any(
                w in term_name_lower for w in ["cooked", "roasted", "fried", "boiled"]
            )
            else 0.0
        )  # is_cooked
        features[11] = (
            1.0
            if any(
                w in term_name_lower for w in ["canned", "frozen", "dried", "preserved"]
            )
            else 0.0
        )  # is_preserved
        features[12] = (
            1.0 if any(w in term_name_lower for w in ["fermented", "pickled"]) else 0.0
        )  # is_fermented
        features[13] = (
            1.0 if any(w in term_name_lower for w in ["processed", "prepared"]) else 0.0
        )  # is_processed

        # Source features (14-17) - check ancestors
        features[14] = (
            1.0 if FOODON_CATEGORIES["plant"] in ancestors else 0.0
        )  # source_plant
        # Animal source: check for animal-related ancestors
        animal_keywords = ["animal", "meat", "poultry", "beef", "pork", "chicken"]
        features[15] = (
            1.0 if any(kw in str(ancestors).lower() for kw in animal_keywords) else 0.0
        )  # source_animal
        features[16] = (
            1.0 if "fungus" in str(ancestors).lower() else 0.0
        )  # source_fungus
        features[17] = 0.0  # source_mineral (salt, etc.) - rare

        # Numeric features (18-19)
        features[18] = min(len(ancestors) / 10.0, 1.0)  # hierarchy depth normalized
        features[19] = confidence  # match confidence

        return features


# Singleton instance for reuse
_instance = None


def get_extractor() -> FoodOnFeatureExtractor:
    """Get or create singleton FoodOnFeatureExtractor instance."""
    global _instance
    if _instance is None:
        _instance = FoodOnFeatureExtractor()
    return _instance
