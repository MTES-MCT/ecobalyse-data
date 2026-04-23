# Ecosystemic Services Data

Input data for computing ecosystemic services of food ingredients.

## Files

| File | Description |
|------|-------------|
| `feed.json` | Animal feed composition: maps each live animal/egg/milk alias to its feed ingredients and quantities. Doesn't include meat ingredients. |
| `animal_to_meat.json` | Link the meat ingredients to their respective live animals. Indicates the ratio of live animal quantity needed to produce 1 kg of meat. |
| `ecosystemic_factors.csv` | Ecosystemic service factors per crop group and scenario (hedges, plotSize, cropDiversity, livestockDensity) |
| `ugb.csv` | UGB (Unite Gros Betail) conversion factors per animal group and product |
| `es_transformations.png` | Visualization of the transformation functions applied to ecosystemic factors |

## feed.json

Each key is a live animal/egg/milk ingredient alias. The value is an object mapping feed ingredient aliases to quantities.
Each quantity is expressed in the unit of the processes except `grazed-grass-...` which is in m2.year
For example `silage-maize-fr-2025` is in kg so to produce 1 kg of `milk-2025` you need :
- 0.175 m2.year of `grazed-grass-permanent-2025`
- 0.349 kg of `silage-maize-fr-2025` and so on...

Example:

```json
{
  "milk-2025": {
    "grazed-grass-permanent-2025": 0.175,
    "grazed-grass-temporary-2025": 0.438,
    "silage-maize-fr-2025": 0.349,
    "soft-wheat-fr": 0.0857,
    "soybean-br-deforestation": 0.0646
  },
  "beef-cattle-conventional-fr-live": {
    "grazed-grass-permanent-2025": 16.2318,
    "grazed-grass-temporary-2025": 2.18543,
    "silage-maize-fr-2025": 1.47682,
    "soft-wheat-fr": 0.549669,
    "soybean-br-deforestation": 0.231788
  },
}
```

## animal_to_meat.json

```json
{
"beef-cattle-conventional-fr-live": {
    "beef-with-bone": 1.51,
    "beef-without-bone": 1.89,
    "ground-beef-2025": 2.31
  },
}
```

To produce 1 kg of `beef-with-bone` you need 1.51 kg of live animal `beef-cattle-conventional-fr-live` so the feed necessary is 1.51 times the feed of `beef-cattle-conventional-fr-live` (which is in feed.json)
