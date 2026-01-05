# Food Ingredient Reference Data for metadata

Reference datasets that were used for predicting food new ingredient metadata.
These files are copied from the ecobalyse-method-tooling repository

## Files

| File | Description |
|------|-------------|
| `food_type.csv` | Food category mapping (vegetable, fruit, meat, fish_seafood, dairy, grain, nut_oilseed, spice_condiment) |
| `nova_classification.csv` | NOVA 1-4 processing level classification |
| `processing_state.csv` | Raw/processed state mapping |
| `transport_cooling.csv` | Refrigeration needs (none, always, once) |
| `cropgroup.csv` | Agricultural crop groups (plant products) |
| `density.csv` | Mass per volume (kg/L) - custom values |
| `fao_density.csv` | Mass per volume (kg/L) - FAO reference |
| `inedible_part.csv` | Non-edible fraction (0-1) |
| `agb_inedible.csv` | Non-edible fraction - Agribalyse reference |
| `cooked_to_raw.csv` | Weight change after cooking |

## Sources

- **FAO** - Density reference values
- **Agribalyse/CIQUAL** - Cooking ratios, inedible parts
- **FoodOn Ontology** - Food classification
