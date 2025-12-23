This is a separated experiment to compute metadata from a list of new ingredients

# Ingredient Metadata Prediction System

## Directory Structure

```
predict/
├── source/
│   └── new_ingredient_FR.csv      # Input: new ingredients to predict
├── generated/
│   ├── predictions.csv            # Output: CSV with predictions + confidence
│   └── new_activities.json        # Output: activities.json format
├── reference/
│   ├── food_type.csv              # custom food type mappings
│   ├── processing_state.csv       # custom processing state mappings
│   ├── cropgroup.csv              # custom crop group mappings
│   ├── density.csv                # custom density values
│   ├── inedible_part.csv          # custom inedible part percentages
│   ├── fao_density.csv            # FAO density reference
│   ├── agb_inedible.csv           # AGB inedible reference
│   ├── cooked_to_raw.csv          # custom cooked/raw ratios
│   ├── transport_cooling.csv      # custom transport cooling
├── export.py                      # Main export script
├── predict.py                     # Predictor class
└── foodon_loader.py               # FoodOn ontology loader
```

## Usage

```bash
uv run export.py                # Export predictions to CSV + JSON
uv run export.py --clear-cache  # Clear translation cache first
```

The `fao_density.csv` and `agb_inedible.csv` should not be changed, they are original AGB and FAO values.
All other reference files can be adapted at will.

## Architecture

### Training Phase

```
ingredients.json ──────┐
(existing              │
 ingredients)          │
                       ▼
            ┌──────────────────────┐
            │  French→English      │
            │  Translation         │
            │  (Helsinki-NLP)      │
            └──────────┬───────────┘
                       │
                       ▼
            ┌──────────────────────┐      ┌─────────────────────────────┐
            │  Feature Extraction  │      │   Reference CSV Data        │
            │  per ingredient      │      │                             │
            │                      │      │  • food_type.csv            │
            │  ┌────────────────┐  │      │  • processing_state.csv     │
            │  │ FoodOn Ontology│  │      │  • cropgroup.csv            │
            │  │ (52K terms)    │  │      │  • density.csv              │
            │  │ → 20 dims      │  │      │  • inedible_part.csv        │
            │  └────────────────┘  │      │  • cooked_to_raw.csv        │
            │  ┌────────────────┐  │      │  • transport_cooling.csv    │
            │  │ Regex Patterns │  │      └─────────────┬───────────────┘
            │  │ (25 binary)    │  │                    │
            │  └────────────────┘  │                    │
            └──────────┬───────────┘                    │
                       │                                │
                       ▼                                ▼
            ┌─────────────────────────────────────────────────────────┐
            │           NearestNeighborMatcher (one per field)        │
            │                                                         │
            │   foodType_matcher ←── food_type.csv only               │
            │   processingState_matcher ←── ingredients + CSV         │
            │   cropGroup_matcher ←── ingredients + CSV               │
            │   transportCooling_matcher ←── ingredients + CSV        │
            │   density_matcher ←── ingredients + CSV                 │
            │   inediblePart_matcher ←── ingredients + CSV            │
            │   rawToCookedRatio_matcher ←── ingredients + CSV        │
            └─────────────────────────────────────────────────────────┘
```

### Prediction Phase

```
New Ingredient
┌─────────────────────────┐
│ name: "Watermelon"      │
│ activityName: ".." (opt)│
└───────────┬─────────────┘
            │
            ▼
┌───────────────────────────────────────────────────────────────────┐
│                    NearestNeighborMatcher.predict()               │
│                                                                   │
│   PRIORITY 1: Exact Text Match (confidence = 1.0)                 │
│   ┌─────────────────────────────────────────────────────────┐     │
│   │ "watermelon" == "watermelon" in reference?              │     │
│   └─────────────────────────────────────────────────────────┘     │
│                          │                                        │
│                          ▼ (if no exact match)                    │
│   PRIORITY 2: Substring Match (confidence = 0.95)                 │
│   ┌─────────────────────────────────────────────────────────┐     │
│   │ Minimum 5 characters required (to avoid false matches)  │     │
│   │ Longest match wins                                       │     │
│   └─────────────────────────────────────────────────────────┘     │
│                          │                                        │
│                          ▼ (if no substring match)                │
│   PRIORITY 3: FoodOn + Regex Similarity (confidence = cosine)     │
│   ┌─────────────────────────────────────────────────────────┐     │
│   │ 45-dim feature vector: 20 FoodOn + 25 regex             │     │
│   │ Cosine similarity with all reference items              │     │
│   └─────────────────────────────────────────────────────────┘     │
└───────────────────────────────────────────────────────────────────┘
            │
            ▼
┌───────────────────────────────────────────────────────────────────┐
│                      Predicted Metadata                           │
│                                                                   │
│   foodType: "fruit"                                               │
│   processingState: "raw"                                          │
│   cropGroup: "LEGUMES-FLEURS"                                     │
│   transportCooling: "always"                                      │
│   density: 1.0                                                    │
│   inediblePart: 0.35                                              │
│   rawToCookedRatio: 1.0                                           │
└───────────────────────────────────────────────────────────────────┘
```

## Output Format

### predictions.csv

| Column | Description |
|--------|-------------|
| name | Ingredient name |
| categories | Predicted categories (comma-separated) |
| foodType | Food type + match name + confidence |
| processingState | Processing state + match + confidence |
| transportCooling | Transport cooling + match |
| cropGroup | Crop group + match + confidence |
| density | Density value + match + confidence |
| inediblePart | Inedible part + match + confidence |
| rawToCookedRatio | Raw-to-cooked ratio + match + confidence |

### new_activities.json

Match info includes source file and confidence:

```json
{
  "ingredientDensity": 0.9,
  "ingredientDensityMatch": {
    "file": "density.csv",
    "name": "bell pepper",
    "confidence": 0.95
  }
}
```

## Feature Extraction

### FoodOn Ontology Features (20 dimensions)

```
Query: "Watermelon"
         ↓
   FoodOn Ontology (52,628 food terms)
         ↓
   Find top-20 most similar terms by word overlap
         ↓
   [0.8, 0.6, 0.4, 0.3, ...] (20 similarity scores)
```

### Regex Binary Features (25 dimensions)

```python
DETECTION_PATTERNS = {
    "is_meat": r"\b(viande|meat|boeuf|porc|poulet|...)\b",
    "is_fish": r"\b(poisson|fish|saumon|thon|...)\b",
    "is_dairy": r"\b(lait|milk|fromage|cheese|...)\b",
    "is_vegetable": r"\b(légume|vegetable|carotte|...)\b",
    "is_fruit": r"\b(fruit|pomme|orange|...)\b",
    "is_frozen": r"\b(surgelé|frozen|congelé)\b",
    "is_canned": r"\b(conserve|canned|boîte)\b",
    # ... 25 total patterns
}
```

## Confidence Scores

| Match Type | Confidence |
|------------|------------|
| Exact match | 1.0 |
| Substring match (min 5 chars) | 0.95 |
| FoodOn + regex similarity | 0.0 - 1.0 (cosine) |

## Example

Input: `{"name": "Salmon fillet"}`

```
Step 1: Translate → "Salmon fillet" (already English)

Step 2: For each field, find best match:
  ├─ foodType:         fish_seafood (rule: is_fish pattern)
  ├─ processingState:  raw (nearest neighbor)
  ├─ cropGroup:        N/A (animal product)
  ├─ transportCooling: always (rule: fresh fish)
  ├─ density:          1.05 (nearest neighbor)
  ├─ inediblePart:     0.0 (nearest neighbor)
  └─ rawToCookedRatio: 0.75 (nearest neighbor)

Output: {
  "foodType": "fish_seafood",
  "processingState": "raw",
  "transportCooling": "always",
  "density": 1.05,
  "inediblePart": 0.0,
  "rawToCookedRatio": 0.75
}
```
