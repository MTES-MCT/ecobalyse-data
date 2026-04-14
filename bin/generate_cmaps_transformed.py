#!/usr/bin/env python3
"""Generate CMAPS transformed ingredient entries for activities_to_create.json and activities.json.

Reads the Wainstain CSV and produces new entries following the plan in .claude/cmaps_transformed_ingredients.md.
"""

import csv
import json
import re
import uuid
from pathlib import Path

# ── Paths ──────────────────────────────────────────────────────────────────────

CSV_PATH = Path(
    "/Users/paulboosz/Downloads/Wainstain ingrédients transformés - data_2.csv"
)
PROJECT_DIR = Path(__file__).resolve().parent.parent
ATC_PATH = PROJECT_DIR / "activities_to_create.json"
ACT_PATH = PROJECT_DIR / "activities.json"
OUT_ATC = PROJECT_DIR / "cmaps_activities_to_create.json"
OUT_ACT = PROJECT_DIR / "cmaps_activities.json"

# ── Energy exchanges ──────────────────────────────────────────────────────────

ELEC_GLO = {
    "database": "Ecoinvent 3.9.1",
    "name": "electricity, high voltage//[GLO] market group for electricity, high voltage",
}
HEAT_GLO = {
    "database": "Ecoinvent 3.9.1",
    "name": "heat, district or industrial, natural gas//[RoW] heat production, natural gas, at industrial furnace low-NOx >100kW",
}
BIOWASTE_GLO = {
    "database": "Ecoinvent 3.9.1",
    "name": "biowaste//[RoW] market for biowaste",
}

ELEC_FR = {
    "database": "Agribalyse 3.2",
    "name": "Electricity, high voltage {FR}| production mix | Cut-off, S - Copied from Ecoinvent U",
}
HEAT_FR = {
    "database": "Agribalyse 3.2",
    "name": "Heat, district or industrial, natural gas {FR}| heat and power co-generation, natural gas, conventional power plant, 100MW electrical | Cut-off, S - Copied from Ecoinvent U",
}
BIOWASTE_FR = {
    "database": "Ecoinvent 3.9.1",
    "name": "biowaste//[FR] market for biowaste",
}

# ── FR energy exception labels (stripped) ─────────────────────────────────────

FR_ENERGY_LABELS = {
    "Purée - Figue (CMAPS) - OI",
    "Purée - Prune (CMAPS) - OI",
    "Farine de riz - OI",
    "Farine de maïs - OI",
    "Farine d'orge - OI",
    "Farine de soja - OI",
    "Farine de blé tendre, froment ou millet - OI",
    "Farine de riz - OI BIO",
    "Farine de soja - OI BIO",
}

# ── ICV name/database corrections ────────────────────────────────────────────
# CSV ICV names that don't match exactly what's in Brightway databases.
# Keys: original CSV ICV name → dict with optional "name", "database", "location" overrides.

ICV_CORRECTIONS = {
    # Agribalyse name mismatches (missing suffix)
    "Avocado {GLO}| avocado production | Cut-off, U": {
        "name": "Avocado {GLO}| production | Cut-off, U - Adapted from Ecoinvent U",
    },
    "Cow milk {RoW}| milk production, from cow | Cut-off, U": {
        "name": "Cow milk {RoW}| milk production, from cow | Cut-off, U - Copied from Ecoinvent U",
    },
    "Olive {ES}| olive production | Cut-off, U": {
        "name": "Olive {ES}| olive production | Cut-off, U - Adapted from Ecoinvent U",
    },
    # WFLDB typo
    "Chicken egg, poultry industrial laying systems, at farm (WFLDB)": {
        "name": "Chicken egg, poultry laying industrial systems, at farm (WFLDB)",
    },
    # WFLDB name variants that don't exist
    "Barley grain, non-irrigated, at farm (WFLDB)": {
        "name": "Barley grain, at farm (WFLDB)",
    },
    "Tomato, fresh grade, open field, at farm (WFLDB)": {
        "name": "Tomato, fresh grade, at farm (WFLDB)",
    },
    # WFLDB location: walnut only exists at US, not GLO
    "Walnut, in shell, dried, at farm (WFLDB)": {
        "location": "US",
    },
    # Entries genuinely in Ecoinvent 3.9.1 (names in Brightway product//[loc] format)
    "Sweet corn {US-MN}| sweet corn production | Cut-off, U": {
        "name": "sweet corn//[US] sweet corn production",
        "database": "Ecoinvent 3.9.1",
    },
    "Fava bean {CA-AB}| fava bean production | Cut-off, U": {
        "name": "fava bean//[CA-AB] fava bean production",
        "database": "Ecoinvent 3.9.1",
    },
    "Lettuce {GLO}| lettuce production, in heated greenhouse | Cut-off, U": {
        "name": "lettuce//[GLO] lettuce360 production, in heated greenhouse",
        "database": "Ecoinvent 3.9.1",
    },
}

# ── EB_id → cropGroup mapping ────────────────────────────────────────────────

EB_ID_CROP_GROUP = {
    # Fruits
    "EB_id0164": "VERGERS",  # Raspberry
    "EB_id0020": "VERGERS",  # Blackberry
    "EB_id0077": "VERGERS",  # Peach (proxy fig)
    "EB_id0092": "VERGERS",  # Cherry (proxy plum)
    "EB_id0006": "VERGERS",  # Apricot
    "EB_id0005": "VERGERS",  # Apple
    "EB_id0146": "VERGERS",  # Pear
    "EB_id0137": "VERGERS",  # Orange
    "EB_id0108": "VERGERS",  # Lemon
    "EB_id0118": "VERGERS",  # Mango
    "EB_id0151": "VERGERS",  # Pineapple
    "EB_id0012": "VERGERS",  # Banana
    "EB_id0143": "VERGERS",  # Peach
    "EB_id0203": "VERGERS",  # Strawberry
    "EB_id0009": "VERGERS",  # Avocado
    "EB_id0040": "VERGERS",  # Cherry
    # Nuts
    "EB_id0002": "FRUITS A COQUES",  # Almond
    "EB_id0095": "FRUITS A COQUES",  # Hazelnut
    "EB_id0222": "FRUITS A COQUES",  # Walnut
    "EB_id0144": "AUTRES OLEAGINEUX",  # Peanut
    # Vegetables
    "EB_id0034": "LEGUMES-FLEURS",  # Carrot
    "EB_id0215": "LEGUMES-FLEURS",  # Tomato
    "EB_id0063": "LEGUMES-FLEURS",  # Tomato (proxy cucumber)
    "EB_id0080": "LEGUMES-FLEURS",  # French bean (green)
    "EB_id0174": "LEGUMES-FLEURS",  # Lettuce
    "EB_id0225": "LEGUMES-FLEURS",  # French bean (white)
    "EB_id0136": "LEGUMES-FLEURS",  # Onion (proxy garlic)
    "EB_id0140": "LEGUMES-FLEURS",  # Parsley
    "EB_id0135": "OLIVIERS",  # Olive
    # Legumes
    "EB_id0230": "PROTEAGINEUX",  # Winter pea
    "EB_id0078": "PROTEAGINEUX",  # Fava bean
    # Cereals
    "EB_id0057": "MAIS GRAIN ET ENSILAGE",  # Maize
    "EB_id0165": "RIZ",  # Rice
    "EB_id0227": "ORGE",  # Barley
    "EB_id0192": "AUTRES OLEAGINEUX",  # Soybean
    "EB_id0189": "BLE TENDRE",  # Soft wheat
    "EB_id0133": "AUTRES CEREALES",  # Oat
    # Vine
    "EB_id0090": "VIGNES",  # Grape
    # Animal products → None (handled later)
    "EB_id0060": None,  # Cow milk
    "EB_id0185": None,  # Sheep milk
    "EB_id0070": None,  # Egg
    "EB_idV03": None,  # Broiler
    "EB_idV01": None,  # Beef
    "EB_idV07": None,  # Pig
}

# ── Product info mapping ─────────────────────────────────────────────────────
# base_label (after stripping origin suffix) → {en, type}
# type: juice, puree, canned, fresh_fruit, fresh_veg, egg, nut, wine,
#       frozen, cheese, fresh_dairy, butter, dried, flour, meat

PRODUCT_INFO = {
    # Jus
    "Jus - Framboise (CMAPS)": {"en": "Raspberry juice", "type": "juice"},
    "Jus - Mûre (CMAPS)": {"en": "Blackberry juice", "type": "juice"},
    # Purée
    "Purée - Figue (CMAPS)": {"en": "Fig puree", "type": "puree"},
    "Purée - Prune (CMAPS)": {"en": "Plum puree", "type": "puree"},
    # Appertisé
    "Haricot blanc. appertisé. égoutté": {
        "en": "White bean, canned drained",
        "type": "canned",
    },
    "Maïs doux. appertisé. égoutté": {
        "en": "Sweet corn, canned drained",
        "type": "canned",
    },
    "Tomate. pelée. appertisée. égouttée": {
        "en": "Tomato, peeled canned drained",
        "type": "canned",
    },
    # Fresh cut fruits
    "Cerise. dénoyautée. crue": {"en": "Cherry, pitted raw", "type": "fresh_fruit"},
    "Abricot. dénoyauté. cru": {"en": "Apricot, pitted raw", "type": "fresh_fruit"},
    "Ananas. pulpe. cru": {"en": "Pineapple, pulp raw", "type": "fresh_fruit"},
    "Banane. pulpe. crue": {"en": "Banana, pulp raw", "type": "fresh_fruit"},
    "Mangue. pulpe. crue": {"en": "Mango, pulp raw", "type": "fresh_fruit"},
    "Orange. pulpe. crue": {"en": "Orange, pulp raw", "type": "fresh_fruit"},
    "Pêche. pulpe et peau. crue": {
        "en": "Peach, pulp and skin raw",
        "type": "fresh_fruit",
    },
    "Poire. pulpe. crue": {"en": "Pear, pulp raw", "type": "fresh_fruit"},
    "Pomme. pulpe. crue": {"en": "Apple, pulp raw", "type": "fresh_fruit"},
    "Citron. pulpe, cru": {"en": "Lemon, pulp raw", "type": "fresh_fruit"},
    "Avocat. pulpe. cru": {"en": "Avocado, pulp raw", "type": "fresh_fruit"},
    # Fresh cut vegetables
    "Carotte. découpée, crue": {"en": "Carrot, cut raw", "type": "fresh_veg"},
    "Concombre. pulpe. cru": {"en": "Cucumber, pulp raw", "type": "fresh_veg"},
    "Haricot vert, découpé, cru": {"en": "Green bean, cut raw", "type": "fresh_veg"},
    "Salade crue, découpée, nettoyée (laitue, mache, mesclun, jeunes pousses, scarole, pissenlit, roquette, cresson)": {
        "en": "Lettuce, cut washed raw",
        "type": "fresh_veg",
    },
    "Petits pois, écossés, crus": {"en": "Pea, shelled raw", "type": "fresh_veg"},
    "Olive verte, dénoyautée": {"en": "Green olive, pitted", "type": "fresh_veg"},
    # Nuts
    "Amande, décortiquée, avec peau": {
        "en": "Almond, shelled with skin",
        "type": "nut",
    },
    "Noisette, décortiquée": {"en": "Hazelnut, shelled", "type": "nut"},
    "Noix. décortiquée, fraîche ou sèche": {"en": "Walnut, shelled", "type": "nut"},
    "Cacahuète ou Arachide décortiquée (cuites, grillées, salées, bouilles)": {
        "en": "Peanut, shelled",
        "type": "nut",
    },
    # Egg
    "Oeuf, décoquillé, de poule, de cane ou d'oie, cru": {
        "en": "Egg, shelled raw",
        "type": "egg",
    },
    # Wine
    "Vin blanc (sec)": {"en": "White wine, dry", "type": "wine"},
    # Frozen
    "Haricot flageolet. surgelé": {
        "en": "Flageolet bean, frozen",
        "type": "frozen",
    },
    "Maïs doux. surgelé. cru": {"en": "Sweet corn, frozen raw", "type": "frozen"},
    "Fraise. crue, surgelé": {"en": "Strawberry, frozen raw", "type": "frozen"},
    "Fruits rouges. crus (framboises. fraises. groseilles. cassis), surgelé": {
        "en": "Red berries, frozen raw",
        "type": "frozen",
    },
    # Dried
    "Persil. séché": {"en": "Parsley, dried", "type": "dried"},
    "Ail séché. poudre": {"en": "Garlic, dried powder", "type": "dried"},
    # Flour
    "Farine de riz": {"en": "Rice flour", "type": "flour"},
    "Farine de maïs": {"en": "Corn flour", "type": "flour"},
    "Farine d'orge": {"en": "Barley flour", "type": "flour"},
    "Farine de soja": {"en": "Soy flour", "type": "flour"},
    "Farine de blé tendre, froment ou millet": {
        "en": "Soft wheat flour",
        "type": "flour",
    },
    "Farine d'avoine (CMAPS)": {"en": "Oat flour", "type": "flour"},
    # Meat
    "Pièce de volaille et lapin, désossée, crue (poulet, dinde, chapon, canard, oie, lapin)": {
        "en": "Poultry, boneless raw",
        "type": "meat",
    },
    "Pièces de boeuf, désossée, crue (côte, épaule, gite, joue, jarret, rosbif, onglet, bavette...)": {
        "en": "Beef, boneless raw",
        "type": "meat",
    },
    "Pièces de porc, désossée, crue (poitrine, longe, jarret, cote, rouelle, carre, filet, roti, palette, jambonneau, escalope, travers, échine)": {
        "en": "Pork, boneless raw",
        "type": "meat",
    },
    # Cheese - simple proper names
    "Chaource": {"en": "Chaource cheese", "type": "cheese"},
    "Cheddar": {"en": "Cheddar cheese", "type": "cheese"},
    "Raclette (fromage)": {"en": "Raclette cheese", "type": "cheese"},
    "Comté": {"en": "Comte cheese", "type": "cheese"},
    "Cantal. Salers ou Laguiole": {"en": "Cantal cheese", "type": "cheese"},
    "Coulommiers": {"en": "Coulommiers cheese", "type": "cheese"},
    "Emmental ou emmenthal": {"en": "Emmental cheese", "type": "cheese"},
    "Gorgonzola": {"en": "Gorgonzola cheese", "type": "cheese"},
    "Gouda": {"en": "Gouda cheese", "type": "cheese"},
    "Gruyère": {"en": "Gruyere cheese", "type": "cheese"},
    "Beaufort": {"en": "Beaufort cheese", "type": "cheese"},
    "Mimolette": {"en": "Mimolette cheese", "type": "cheese"},
    "Munster": {"en": "Munster cheese", "type": "cheese"},
    "Parmesan": {"en": "Parmesan cheese", "type": "cheese"},
    "Reblochon": {"en": "Reblochon cheese", "type": "cheese"},
    "Roquefort": {"en": "Roquefort cheese", "type": "cheese"},
    "Saint-Marcellin": {"en": "Saint-Marcellin cheese", "type": "cheese"},
    "Camembert": {"en": "Camembert cheese", "type": "cheese"},
    "Brie. sans précision": {"en": "Brie cheese", "type": "cheese"},
    "Pont l'Évêque": {"en": "Pont l'Eveque cheese", "type": "cheese"},
    # Cheese - complex names
    "Fourme d'Ambert": {"en": "Fourme d'Ambert cheese", "type": "cheese"},
    "Fromage fondu": {"en": "Processed cheese", "type": "cheese"},
    "Fromage bleu d'Auvergne": {"en": "Blue cheese Auvergne", "type": "cheese"},
    "Fromage type feta. au lait de vache": {
        "en": "Feta type cheese, cow milk",
        "type": "cheese",
    },
    "Fromage 100% brebis type Feta": {
        "en": "Feta type cheese, sheep milk",
        "type": "cheese",
    },
    "Fromage à pâte ferme environ 14% MG type Masdaam à teneur réduite en MG": {
        "en": "Reduced fat firm cheese, Maasdam type",
        "type": "cheese",
    },
    "Fromage de chèvre sec": {"en": "Dry goat cheese", "type": "cheese"},
    "Fromage de chèvre (frais, bûche, affiné, pasteurisé, crottin)": {
        "en": "Goat cheese, fresh to aged",
        "type": "cheese",
    },
    "Fromage de chèvre sec (chabichou, picodon, crottin de Chavignol)": {
        "en": "Dry goat cheese, chabichou type",
        "type": "cheese",
    },
    "Spécialité fromagère non affinée à tartiner 20 à 40 % MG nature ou aromatisée (ex: ail et fines herbes)": {
        "en": "Spread cheese, 20-40pct fat",
        "type": "cheese",
    },
    "Tomme ou tome de vache": {"en": "Tomme cheese, cow milk", "type": "cheese"},
    "Mozzarella au lait de vache": {"en": "Mozzarella, cow milk", "type": "cheese"},
    "Mont d'or ou Vacherin du Haut-Doubs (produit en France) ou Vacherin-Mont d'Or (produit en Suisse)": {
        "en": "Mont d'Or cheese",
        "type": "cheese",
    },
    # Fresh dairy
    "Faisselle. 6% MG environ": {"en": "Faisselle, 6pct fat", "type": "fresh_dairy"},
    "Fromage blanc nature. 3% MG environ": {
        "en": "Fromage blanc, 3pct fat",
        "type": "fresh_dairy",
    },
    "Fromage blanc nature. gourmand. 8% MG environ": {
        "en": "Fromage blanc, 8pct fat",
        "type": "fresh_dairy",
    },
    "Fromage frais type petit suisse. nature. 4% MG environ": {
        "en": "Petit suisse, 4pct fat",
        "type": "fresh_dairy",
    },
    "Fromage frais type petit suisse. nature. 10% MG environ": {
        "en": "Petit suisse, 10pct fat",
        "type": "fresh_dairy",
    },
    "Fromage blanc ou frais type petit suisse, nature, 0% MG": {
        "en": "Fromage blanc, 0pct fat",
        "type": "fresh_dairy",
    },
    "Yaourt à la grecque. au lait de brebis": {
        "en": "Greek yogurt, sheep milk",
        "type": "fresh_dairy",
    },
    # Butter / dairy fat
    "Beurre à 82% MG ou huile de beurre": {
        "en": "Butter, 82pct fat",
        "type": "butter",
    },
    "Beurre à 60-62% MG. à teneur réduite en matière grasse. doux": {
        "en": "Butter, 60-62pct fat reduced",
        "type": "butter",
    },
    "Beurre à 39-41% MG. léger. doux": {
        "en": "Butter, 39-41pct fat light",
        "type": "butter",
    },
    'Matière grasse laitière à 25% MG. légère. "à tartiner". doux': {
        "en": "Dairy spread, 25pct fat",
        "type": "butter",
    },
    'Matière grasse laitière à 20% MG. légère. "à tartiner". doux': {
        "en": "Dairy spread, 20pct fat",
        "type": "butter",
    },
}

# ── Product type → metadata rules ─────────────────────────────────────────────

TYPE_INGREDIENT_CATEGORIES = {
    "juice": ["vegetable_processed"],
    "puree": ["vegetable_processed"],
    "canned": ["vegetable_processed"],
    "fresh_fruit": ["vegetable_fresh"],
    "fresh_veg": ["vegetable_fresh"],
    "egg": ["animal_product"],
    "nut": ["nut_oilseed_raw"],
    "wine": ["misc"],
    "frozen": ["vegetable_processed"],
    "cheese": ["dairy_product"],
    "fresh_dairy": ["dairy_product"],
    "butter": ["dairy_product"],
    "dried": ["spice_condiment_additive"],
    "flour": ["grain_processed"],
    "meat": ["animal_product"],
}

TYPE_TRANSPORT_COOLING = {
    "juice": "always",
    "puree": "always",
    "canned": "none",
    "fresh_fruit": "always",
    "fresh_veg": "always",
    "egg": "always",
    "nut": "none",
    "wine": "none",
    "frozen": "always",
    "cheese": "always",
    "fresh_dairy": "always",
    "butter": "always",
    "dried": "none",
    "flour": "always",
    "meat": "always",
}

# Animal product types (no cropGroup)
ANIMAL_TYPES = {"egg", "cheese", "fresh_dairy", "butter", "meat"}


# ── Helper functions ──────────────────────────────────────────────────────────


def strip_origin_suffix(label: str) -> str:
    """Strip origin/bio suffix: '- FR', '- OI', '- FR BIO', '- OI BIO'."""
    return re.sub(r"\s*-\s*(FR|OI)(\s+BIO)?\s*$", "", label).strip()


def slugify(text: str) -> str:
    """Convert text to a URL-friendly slug."""
    text = text.lower()
    text = text.replace("'", "").replace("'", "")
    text = re.sub(r"[^a-z0-9\s-]", "", text)
    text = re.sub(r"[\s]+", "-", text.strip())
    return text.strip("-")


def _clean_display_name(base_label: str, origin: str, is_bio: bool) -> str:
    """Build a clean French display name from the base label and origin.

    - Replace '. ' and '. ' separators with ', '
    - Append readable origin: 'FR', 'FR BIO', 'Origine Inconnue', 'Origine Inconnue BIO'
    """
    # Normalize separators: '. ' → ', ' and strip extra spaces
    name = base_label
    name = re.sub(r"\.\s+", ", ", name)
    # Also handle '. ' at end
    name = name.rstrip(". ")
    # Build origin suffix
    if origin == "FR":
        suffix = "FR BIO" if is_bio else "FR"
    else:
        suffix = "Origine Inconnue BIO" if is_bio else "Origine Inconnue"
    return f"{name} {suffix}"


def determine_icv_database(icv_name: str) -> str:
    """Determine which Brightway database an ICV name belongs to.

    Food ingredients are in Agribalyse 3.2 (even Ecoinvent-style names like
    '| Cut-off, U' which are copies/adaptations). Organics with 'organic 2025'
    are in Ginko 2025. WFLDB-suffixed names are in WFLDB. Activities with
    {{alias}} tags are in the Ecobalyse custom database.
    """
    if "organic 2025" in icv_name:
        return "Ginko 2025"
    if icv_name.rstrip().endswith("(WFLDB)"):
        return "WFLDB"
    if "{{" in icv_name:
        return "Ecobalyse"
    return "Agribalyse 3.2"


def is_fr_energy(label: str) -> bool:
    """Check if this label should use FR energy mix instead of GLO."""
    return label.strip() in FR_ENERGY_LABELS


def get_scenario(origin: str, is_bio: bool) -> str:
    if is_bio:
        return "organic"
    if origin == "OI":
        return "import"
    return "reference"


def get_default_origin(origin: str) -> str:
    if origin == "FR":
        return "France"
    return "OutOfEuropeAndMaghreb"


def get_ingredient_categories(product_type: str, is_bio: bool) -> list:
    cats = list(TYPE_INGREDIENT_CATEGORIES.get(product_type, ["misc"]))
    if is_bio:
        cats.append("organic")
    return cats


# ── CSV Parsing ───────────────────────────────────────────────────────────────


def parse_csv(csv_path: Path) -> list[dict]:
    """Parse the CSV and return structured row dicts."""
    rows = []
    with open(csv_path, "r", encoding="utf-8") as f:
        reader = csv.reader(f)
        next(reader)  # skip header
        for row_num, row in enumerate(reader, start=2):
            if not row or not row[0].strip():
                continue
            label = row[0].strip().strip('"')
            origin = row[1].strip()
            bio = row[2].strip()
            eb_id = row[3].strip()
            icv = row[4].strip().strip('"')

            # Numeric fields - handle potential issues
            try:
                mass_coeff = float(row[8].strip()) if row[8].strip() else 0.0
            except (ValueError, IndexError):
                mass_coeff = 0.0
            try:
                heat = float(row[9].strip()) if row[9].strip() else 0.0
            except (ValueError, IndexError):
                heat = 0.0
            try:
                elec = float(row[10].strip()) if row[10].strip() else 0.0
            except (ValueError, IndexError):
                elec = 0.0
            try:
                biowaste = float(row[11].strip()) if row[11].strip() else 0.0
            except (ValueError, IndexError):
                biowaste = 0.0

            rows.append(
                {
                    "row_num": row_num,
                    "label": label,
                    "origin": origin,
                    "is_bio": bio == "BIO",
                    "eb_id": eb_id,
                    "icv": icv,
                    "mass_coeff": mass_coeff,
                    "heat": heat,
                    "elec": elec,
                    "biowaste": biowaste,
                }
            )
    return rows


# ── Processing ────────────────────────────────────────────────────────────────


def process_row(row: dict) -> dict:
    """Enrich a parsed row with derived fields."""
    label = row["label"]
    base_label = strip_origin_suffix(label)
    origin = row["origin"]
    is_bio = row["is_bio"]
    eb_id = row["eb_id"]
    icv = row["icv"]

    # Product info lookup
    info = PRODUCT_INFO.get(base_label)
    if info is None:
        print(
            f"  WARNING: No product info for base_label='{base_label}' (row {row['row_num']}: {label})"
        )
        info = {"en": base_label, "type": "misc"}

    product_type = info["type"]
    english_name = info["en"]

    # Energy mix
    use_fr_energy = is_fr_energy(label)
    energy_mix = "fr" if use_fr_energy else "glo"

    # Database
    icv_database = determine_icv_database(icv)

    # Location
    location = "FR" if use_fr_energy else "GLO"

    # cropGroup
    crop_group = EB_ID_CROP_GROUP.get(eb_id)
    if product_type in ANIMAL_TYPES:
        crop_group = None  # handled later

    # Scenario
    scenario = get_scenario(origin, is_bio)

    # Metadata alias: no "cmaps", OI→"default", BIO→"organic"
    origin_slug = "default" if origin == "OI" else origin.lower()
    bio_slug = "-organic" if is_bio else ""
    meta_alias = f"{slugify(english_name)}-{origin_slug}{bio_slug}"

    # Display name: clean up punctuation, use readable origin
    display_name = _clean_display_name(base_label, origin, is_bio)

    return {
        **row,
        "base_label": base_label,
        "english_name": english_name,
        "product_type": product_type,
        "energy_mix": energy_mix,
        "icv_database": icv_database,
        "location": location,
        "crop_group": crop_group,
        "scenario": scenario,
        "default_origin": get_default_origin(origin),
        "ingredient_categories": get_ingredient_categories(product_type, is_bio),
        "transport_cooling": TYPE_TRANSPORT_COOLING.get(product_type, "always"),
        "meta_alias": meta_alias,
        "display_name": display_name,
    }


def group_by_recipe(processed_rows: list[dict]) -> dict:
    """Group rows by identical physical recipe (same ICV, amounts, energy mix).

    Returns {recipe_key: [rows]}.
    """
    groups = {}
    for row in processed_rows:
        key = (
            row["icv"],
            row["mass_coeff"],
            row["heat"],
            row["elec"],
            row["biowaste"],
            row["energy_mix"],
        )
        groups.setdefault(key, []).append(row)
    return groups


# ── Generation ────────────────────────────────────────────────────────────────


def make_alias(
    english_name: str, location: str, icv_database: str, icv_name: str
) -> str:
    """Generate a unique-ish alias based on product name and ICV source."""
    alias = slugify(english_name)
    if location == "FR":
        alias += "-fr-energy"
    # ICV source discriminator to avoid collisions between variants
    if "organic 2025" in icv_name or icv_database == "Ginko 2025":
        alias += "-organic"
    elif icv_database == "WFLDB":
        alias += "-wfldb"
    elif icv_database == "Ecobalyse":
        alias += "-eb"
    # Agribalyse 3.2 = default, no suffix
    return alias


def icv_variant_label(icv_name: str, icv_database: str) -> str:
    """Return a short label to disambiguate newName when multiple ICV variants exist."""
    if "organic 2025" in icv_name or icv_database == "Ginko 2025":
        return "organic"
    if icv_database == "WFLDB":
        return "import WFLDB"
    if icv_database == "Ecobalyse":
        return "modified"
    return ""


def generate_activity_to_create(
    recipe_key, rows: list[dict], alias: str, variant: str
) -> dict:
    """Generate one activities_to_create.json entry for a recipe group."""
    first = rows[0]  # representative row
    icv, mass_coeff, heat, elec, biowaste, energy_mix = recipe_key

    # Pick energy exchanges
    if energy_mix == "fr":
        elec_ex, heat_ex, bio_ex = ELEC_FR, HEAT_FR, BIOWASTE_FR
    else:
        elec_ex, heat_ex, bio_ex = ELEC_GLO, HEAT_GLO, BIOWASTE_GLO

    # Build exchanges, applying ICV corrections if needed
    correction = ICV_CORRECTIONS.get(icv, {})
    corrected_name = correction.get("name", icv)
    corrected_db = correction.get("database", first["icv_database"])
    icv_exchange = {
        "amount": mass_coeff,
        "database": corrected_db,
        "name": corrected_name,
    }
    if corrected_db == "WFLDB":
        icv_exchange["location"] = correction.get("location", "GLO")
    exchanges = [icv_exchange]
    if elec > 0:
        # CSV elec values are in MJ, convert to kWh (1 kWh = 3.6 MJ)
        exchanges.append({"amount": round(elec / 3.6, 6), **elec_ex})
    if heat > 0:
        exchanges.append({"amount": heat, **heat_ex})
    if biowaste > 0:
        exchanges.append({"amount": biowaste, **bio_ex})

    # Build newName, adding variant to disambiguate if needed
    base_name = first["english_name"]
    if variant:
        new_name = f"{base_name}, {variant}, CMAPS {{{first['location']}}} U"
    else:
        new_name = f"{base_name}, CMAPS {{{first['location']}}} U"

    return {
        "activityCreationType": "from_scratch",
        "alias": alias,
        "comment": "CMAPS transformed ingredient",
        "database": first["icv_database"],
        "exchanges": exchanges,
        "location": first["location"],
        "newName": new_name,
    }


def generate_activity_entry(recipe_key, rows: list[dict], atc_entry: dict) -> dict:
    """Generate one activities.json entry for a recipe group."""
    metadata = []
    for row in rows:
        meta = {
            "alias": row["meta_alias"],
            "defaultOrigin": row["default_origin"],
            "displayName": row["display_name"],
            "id": str(uuid.uuid4()),
            "inediblePart": 0,
            "ingredientCategories": row["ingredient_categories"],
            "ingredientDensity": 1,
            "rawToCookedRatio": 1,
            "scenario": row["scenario"],
            "scopes": ["food", "food2"],
            "transportCooling": row["transport_cooling"],
            "visible": True,
        }
        if row["crop_group"] is not None:
            meta["cropGroup"] = row["crop_group"]
        metadata.append(meta)

    # Sort metadata by alias for consistency
    metadata.sort(key=lambda m: m["alias"])

    return {
        "activityName": atc_entry["newName"],
        "alias": atc_entry["alias"],
        "categories": ["ingredient", "material"],
        "displayName": rows[0]["display_name"],
        "id": str(uuid.uuid4()),
        "metadata": metadata,
        "scopes": ["food", "food2"],
        "source": "Ecobalyse",
    }


# ── Main ──────────────────────────────────────────────────────────────────────


def main():
    print("Parsing CSV...")
    raw_rows = parse_csv(CSV_PATH)
    print(f"  {len(raw_rows)} rows parsed")

    print("Processing rows...")
    processed = [process_row(r) for r in raw_rows]

    print("Grouping by recipe...")
    groups = group_by_recipe(processed)
    print(f"  {len(groups)} unique recipes")

    print("Generating entries...")

    # First pass: generate aliases and detect collisions
    raw_entries = []
    for recipe_key, rows in groups.items():
        first = rows[0]
        icv = recipe_key[0]
        alias = make_alias(
            first["english_name"], first["location"], first["icv_database"], icv
        )
        variant = icv_variant_label(icv, first["icv_database"])
        raw_entries.append((alias, variant, recipe_key, rows))

    # Deduplicate aliases with counter suffix
    alias_count = {}
    for alias, _, _, _ in raw_entries:
        alias_count[alias] = alias_count.get(alias, 0) + 1

    alias_index = {}
    atc_entries = []
    act_entries = []

    for alias, variant, recipe_key, rows in raw_entries:
        counter_suffix = ""
        if alias_count[alias] > 1:
            idx = alias_index.get(alias, 0) + 1
            alias_index[alias] = idx
            actual_alias = f"{alias}-v{idx}"
            counter_suffix = f"variant {idx}"
        else:
            actual_alias = alias

        # Only include variant label in newName when there are name collisions
        english_name = rows[0]["english_name"]
        needs_variant = (
            sum(
                1
                for _, _, rk, rs in raw_entries
                if rs[0]["english_name"] == english_name
            )
            > 1
        )

        # Build final variant string for newName disambiguation
        name_variant = variant if needs_variant else ""
        if counter_suffix:
            name_variant = (
                f"{name_variant} {counter_suffix}".strip()
                if name_variant
                else counter_suffix
            )

        atc = generate_activity_to_create(recipe_key, rows, actual_alias, name_variant)
        act = generate_activity_entry(recipe_key, rows, atc)
        atc_entries.append(atc)
        act_entries.append(act)

    # Sort by alias
    atc_entries.sort(key=lambda e: e["alias"])
    act_entries.sort(key=lambda e: e["alias"])

    # Final collision check
    atc_aliases = [e["alias"] for e in atc_entries]
    if len(atc_aliases) != len(set(atc_aliases)):
        dupes = {a for a in atc_aliases if atc_aliases.count(a) > 1}
        print(f"  ERROR: Still have duplicate aliases: {dupes}")
        return

    # Write standalone output files for review
    print(f"Writing {len(atc_entries)} entries to {OUT_ATC}...")
    with open(OUT_ATC, "w", encoding="utf-8") as f:
        json.dump(atc_entries, f, indent=2, ensure_ascii=False)

    print(f"Writing {len(act_entries)} entries to {OUT_ACT}...")
    with open(OUT_ACT, "w", encoding="utf-8") as f:
        json.dump(act_entries, f, indent=2, ensure_ascii=False)

    # Also merge into existing files
    print("Merging into existing files...")

    with open(ATC_PATH, "r", encoding="utf-8") as f:
        existing_atc = json.load(f)
    existing_atc.extend(atc_entries)
    with open(ATC_PATH, "w", encoding="utf-8") as f:
        json.dump(existing_atc, f, indent=2, ensure_ascii=False)
    print(f"  activities_to_create.json: {len(existing_atc)} total entries")

    with open(ACT_PATH, "r", encoding="utf-8") as f:
        existing_act = json.load(f)
    existing_act.extend(act_entries)
    with open(ACT_PATH, "w", encoding="utf-8") as f:
        json.dump(existing_act, f, indent=2, ensure_ascii=False)
    print(f"  activities.json: {len(existing_act)} total entries")

    print("Done! Run 'just fix-all' to format the files.")


if __name__ == "__main__":
    main()
