# ecobalyse-data

Gestion des données utilisées pas l’application [Ecobalyse](https://github.com/MTES-MCT/ecobalyse).


## Socle technique et prérequis


Vous devez disposer d’un environnement [NodeJS](https://nodejs.org/fr/) 14+ et `npm` pour l’exécution des scripts et le formattage des fichiers JSON. Pour les scripts disposer de [uv](https://docs.astral.sh/uv/) qui se chargera d’installer python et les dépendances requises sur votre machine.


## Configuration

Les variables d'environnement suivantes doivent être définies :

- `ECOBALYSE_DATA_DIR` : l'emplacement où les fichiers seront exportés, typiquement le dépôt public `/home/user/ecobalyse/public/data`. Une copie locale des impacts non détaillés sera gardée dans `public/data/`.
- `PYTHONPATH` : si vous souhaitez utiliser les scripts Python directement sans passer par npm, assurez-vous d’ajouter le répertoire courant à votre PATH python (`export PYTHONPATH=.`)


Vous devrez préparer les bases de données à importer, elle ne font pas partie du dépôt :
  - Agribalyse : compressé dans un fichier `AGB3.1.1.20230306.CSV.zip` dans un dossier `dbfiles/` au dessus du dépôt
  - Autres bases alimentaire : consultez les noms de fichier dans `import_food.py`
  - Ecoinvent : décompressé dans un dossier `ECOINVENT3.9.1` dans ce même dossier

Par défaut, Brightway stocke les données dans `~/.local/share/Brightway3/`. Il est fortement recommandé de configurer la variable d’environnement `BRIGHTWAY2_DIR` pour mettre les données dans le répertoire où vous souhaitez (le répertoire doit exister, Brightway ne le créera pas à votre place). Si vous souhaitez utiliser docker avec la méthode ci-dessous et souhaitez partager les données Brightway entre votre docker et le Brightway de votre machine, configurez la variable de cette manière :

    export BRIGHTWAY2_DIR=$PWD/.docker/brightway

## Exécution

Pour importer toutes les bases :

    npm run import:all

Pour exporter les fichiers :

    npm run export:all

Pour lancer `jupyter` :

    uv run jupyter lab

# Avec docker

- Installez `docker` et `make`
- Si vous êtes sur Mac avec architecture ARM, affectez 6Go de RAM à Docker dans Docker Desktop :
  Settings → Ressources → Advanced → Memory = 6G
- Lancez **`make`** ce qui va successivement :
  - construire l'image docker ;
  - importer les bases de données dans le projet `default` de Brightway ;
  - exporter les données json utilisées côté front-end, qui pourront ensuite être commitées.

Le processus entier prend environ 1h. En cas de problème vous pouvez redémarrer de zéro en faisant
d'abord un `make clean_data` (qui supprime le volume docker).

## Autres commandes :

- `make image` : pour construire l'image docker choisie
- `make import_food` : pour importer les bases de données alimentaire dans Brightway.
  Assurez-vous d'avoir les bon fichiers de données dans `dbfiles/` au dessus du dépôt
- `make import_ecoinvent` : pour importer Ecoinvent 3.9.1. dans Brightway.
  Assurez-vous d'avoir le bon dossier de données dans `dbfiles/` au dessus du dépôt
- `make import_method` : pour importer EF 3.1 adapted dans Brightway.
  Assurez-vous d'avoir le bon fichier de données dans `dbfiles/` au dessus du dépôt
- `make export_food` : pour exporter les json pour le builder alimentaire
- `make delete_database DB=<dbname>` : pour supprimer une base de données (Ex avec espace: make delete_database DB="Ecoinvent\ 3.9.1")
- `make delete_method` : pour supprimer la méthode EF3.1
- `make sync_datapackages` : lance un fix parfois nécessaire pour la synchro brightway
- `make import` : lance toutes les commandes d'import
- `make export` : lance toutes les commandes d'export
- `make shell` : lance un shell bash à l'intérieur du conteneur
- `make python` : lance un interpréteur Python à l'intérieur du conteneur
- `make jupyter_password` : définit le mot de passe jupyter. Doit être lancé avant son démarrage.
- `make start_notebook` : lance le serveur Jupyter dans le conteneur.
  Peut être précédé du n° de port Jupyter: ex `JUPYTER_PORT=8889`
- `make stop_notebook` : arrête le serveur Jupyter donc aussi le conteneur
- `make clean_data` : supprime toutes les données (celles de brightway et jupyter mais pas les json
  générés)
- `make clean_image` : supprime l'image docker
- `make clean` : lance `clean_data` et `clean_image`

## Travailler dans le conteneur :

Vous pouvez entrer dans le conteneur avec `make shell`.

Le répertoire local `ecobalyse-data` est monté sur le container dans `/home/ecobalyse/ecobalyse-data`
Toutes les données du conteneur, notamment celles de Brightway, sont dans
`/home/ecobalyse/ecobalyse-data/.docker`, et donc dans le répertoire `.docker/` du répertoire courant sur le _host_.
Les fichiers json générés arrivent directement sur place au bon endroit pour être comparés puis commités.

## Lancer le serveur Jupyter de dev

Avant de lancer Jupyter vous pouvez définir son mot de passe avec `make jupyter_password`. Ensuite
vous le démarrez avec `make start_notebook`.

## Lancer le serveur Jupyter pour l'éditeur d'ingrédients

Avant de lancer Jupyter vous pouvez définir son mot de passe avec `make jupyter_password`. Ensuite
vous le démarrez avec `JUPYTER_PORT=8889 make start_notebook`.

## Lancer l'explorateur Brightway

Créez un notebook dans Jupyter puis tapez `import notebooks.explore`, puis shift-Enter

## Lancer l'éditeur de procédés/ingrédients

Créez un notebook dans Jupyter puis tapez `import notebooks.ingredients`, puis shift-Enter

## Remarques

Si l'`export` prend plus de 2 secondes par procédé, c'est un problème d'installation de `pypardiso`
ou de la bibliothèque `mkl` (Math Kernel Library d'Intel) ou une incompatibilité avec l'architecture
CPU utilisée. Dans ce cas c'est le solveur de Scipy qui est utilisé. Il est possible que cela
explique les très légères différences d'arrondi rencontrées dans les résultats.
