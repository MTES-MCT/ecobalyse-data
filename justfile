# https://github.com/casey/just

uv := "PYTHONPATH=. uv"

################################################################################
## Recipes
################################################################################

default:
  @just --list


################################################################################
### Imports

import-all: import-food import-ecoinvent import-method create-activities sync-datapackages

import-food:
  {{uv}} run python import_food.py

import-ecoinvent:
  {{uv}} run python import_ecoinvent.py

import-method:
  {{uv}} run python import_method.py

create-activities:
  {{uv}} run python create_activities.py

sync-datapackages:
  {{uv}} run python common/sync_datapackages.py


################################################################################
### Exports

export-all:
  {{uv}} run python ./bin/export.py processes
  {{uv}} run python ./bin/export.py metadata

export-food:
  {{uv}} run python ./bin/export.py processes --scopes food --merge
  {{uv}} run python ./bin/export.py metadata --scopes food

export-object:
  {{uv}} run python ./bin/export.py processes --scopes object --merge

export-textile:
  {{uv}} run python ./bin/export.py processes --scopes textile --merge
  {{uv}} run python ./bin/export.py metadata --scopes textile

export-veli:
  {{uv}} run python ./bin/export.py processes --scopes veli --merge


################################################################################
### Cleaning

delete-database db:
  {{uv}} run python -m common.delete_database {{db}}

delete-methods:
  {{uv}} run python -m common.delete_methods


################################################################################
### Linting & formatting

check-processes *target:
  {{uv}} run check-jsonschema --schemafile tests/processes-schema.json public/data/processes*.json

check-json +target=".":
  {{uv}} run python ./bin/json_formatter.py {{target}}

fix-json +target=".":
  {{uv}} run python ./bin/json_formatter.py --fix {{target}}

check-python +target=".":
  {{uv}} run ruff check --force-exclude --extend-select I {{target}}
  {{uv}} run ruff format --force-exclude --check {{target}}

fix-python +target=".":
  {{uv}} run ruff check --force-exclude --extend-select I --fix {{target}}
  {{uv}} run ruff format --force-exclude {{target}}

check-all: check-processes check-json check-python

fix-all: fix-json fix-python


################################################################################
### Testing

test:
  {{uv}} run pytest


################################################################################
### Jupyter lab

jupyter:
  {{uv}} run --group jupyter jupyter lab
