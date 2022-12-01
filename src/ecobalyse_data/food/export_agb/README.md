# Exporter la base agribalyse de brightway vers des fichiers json

Au préalable, vérifiez que vous avez bien suivi les instructions du
[README](../../README.md) général, et que vous avez installé le projet comme
indiqué dans le [README](../../../README.md) du repository.

## Exporter les données pour l'explorateur de produits CIQUAL

Lancer le script d'export qui peut prendre plusieurs heures (!).
Il faut préciser le chemin vers le fichier
[impacts.json](https://github.com/MTES-MCT/ecobalyse/blob/master/public/data/impacts.json)
qui contient les coefficients de pondération et de normalisation du score PEF.

    $ python export_ciqual.py <chemin vers le fichier impacts.json>

Il est possible d'utiliser l'option `--max` pour limiter le nombre de produits
ciquals à exporter, et l'option `--no-impacts` pour ne pas calculer les impacts
des procédés (ce qui exportera un fichier `processes-no-impacts.json` au lieu de
`processes.json`) :

    $ python export.py "../../../../../ecobalyse/public/data/impacts.json" --max 1 --no-impacts
    # Beaucoup plus rapide, mais incomplet ;)

Les fichiers résultants sont `processes.json` et `products.json` qui sont à
utiliser par exemple sur le projet
[ecobalyse](https://github.com/MTES-MCT/ecobalyse/) :

    - `processes.json` : à placer dans ecobalyse/public/data/food/processes/explorer.json
    - `products.json` : à placer dans ecobalyse/public/data/food/products.json

Optionnellement, lancer le script de vérification des différences d'impacts :

    $ python checks_ciqual.py

## Exporter les données pour le constructeur de recettes

Lancer le script d'export.
Il faut préciser le chemin vers le fichier
[impacts.json](https://github.com/MTES-MCT/ecobalyse/blob/master/public/data/impacts.json)
qui contient les coefficients de pondération et de normalisation du score PEF,
ainsi que le chemin vers le fichier qui contient les procédés à exporter :
seulement une partie des procédés provenant de agribalyse sont utiles au
constructeur de recettes.

    $ python export_builder.py <chemin vers le fichier impacts.json> <chemin vers le fichier des procédés à exporter>

Exemple :

    $ python export_builder.py ../../../../../ecobalyse/public/data/impacts.json builder_processes_to_export.txt

Les fichiers résultants sont `builder_processes.json` et `ingredients.json` qui sont à
utiliser par exemple sur le projet
[ecobalyse](https://github.com/MTES-MCT/ecobalyse/) :

    - `builder_processes.json` : à placer dans ecobalyse/public/data/food/processes/builder.json
    - `ingredients.json` : à placer dans ecobalyse/public/data/food/ingredients.json
