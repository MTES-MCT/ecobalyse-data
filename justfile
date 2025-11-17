default:
  @just --list

all: import-all export-all

import-all: import-food import-ecoinvent import-method create-activities sync-datapackages

import-food:
  uv run python import_food.py

import-ecoinvent:
  uv run python import_ecoinvent.py

import-method:
  uv run python import_method.py

create-activities:
  uv run python create_activities.py

sync-datapackages:
  uv run python common/sync_datapackages.py

export-all:
  uv run python ./bin/export.py processes && uv run python ./bin/export.py metadata

export-food:
  uv run python ./bin/export.py processes --scopes food --merge && uv run python ./bin/export.py metadata --scopes food

export-object:
  uv run python ./bin/export.py processes --scopes object --merge

export-veli:
  uv run python ./bin/export.py processes --scopes veli --merge

clean:
  uv run python -m common.delete_database && uv run python -m common.delete_methods
