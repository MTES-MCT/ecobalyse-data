# Ecosystemic Services Data

Input data for computing ecosystemic services of food ingredients.

## Files

| File | Description |
|------|-------------|
| `feed.json` | Animal feed composition: maps each animal ingredient alias to its feed ingredients and quantities |
| `ecosystemic_factors.csv` | Ecosystemic service factors per crop group and scenario (hedges, plotSize, cropDiversity, livestockDensity) |
| `ugb.csv` | UGB (Unite Gros Betail) conversion factors per animal group and product |
| `ecs_transformations.png` | Visualization of the transformation functions applied to ecosystemic factors |

## feed.json

Each key is an animal ingredient alias. The value is an object mapping feed ingredient aliases to quantities.
Each quantity is expressed in the unit of the processes.
For example `silage-maize-fr-2025` is in kg so
to produce 1 kg of `milk-2025` you need 0.349 kg of `silage-maize-fr-2025`


Example:

```json
{
  "milk-2025": {
    "grazed-grass-permanent-2025": 0.175,
    "grazed-grass-temporary-2025": 0.438,
    "silage-maize-fr-2025": 0.349,
    "soft-wheat-fr": 0.0857,
    "soybean-br-deforestation": 0.0646
  }
}
```
