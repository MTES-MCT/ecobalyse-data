SHELL := /bin/bash
NAME := ecobalyse-data
ECOBALYSE_DATA_DIR := ${ECOBALYSE_DATA_DIR}
JUPYTER_PORT ?= 8888

export ECOBALYSE_CONTAINER_NAME = $(NAME)
export ECOBALYSE_IMAGE_NAME = $(NAME)

all: import export
import : image import_food import_ecoinvent import_method create_activities sync_datapackages
export: export_food export_textile export_object format

image:
	docker build -t ${ECOBALYSE_IMAGE_NAME} -f docker/Dockerfile .

import_food:
	@./bin/docker.sh uv run python import_food.py

import_method:
	@./bin/docker.sh uv run python import_method.py

import_ecoinvent:
	@./bin/docker.sh uv run python import_ecoinvent.py

create_activities:
	@./bin/docker.sh uv run python create_activities.py

sync_datapackages:
	@./bin/docker.sh uv run python common/sync_datapackages.py

delete_database:
	@./bin/docker.sh uv run python common/delete_database.py "$(DB)"

delete_method:
	@./bin/docker.sh uv run python common/delete_methods.py

export_food:
	@./bin/docker.sh uv run python food/export.py

export_textile:
	@./bin/docker.sh uv run python textile/export.py

export_object:
	@./bin/docker.sh uv run python object/export.py

compare_food:
	@./bin/docker.sh uv run python food/export.py compare

compare_textile:
	@./bin/docker.sh uv run python textile/export.py compare

format:
	@./bin/docker.sh npm run fix:all

python:
	echo Running Python inside the container...
	./bin/docker.sh uv run python

shell:
	echo starting a user shell inside the container...
	./bin/docker.sh bash

jupyter_password:
	echo starting a user shell inside the container...
	./bin/docker.sh uv run jupyter notebook password

start_notebook:

	# Check that the password has been set for jupyter
	@./bin/docker.sh bash -c "if [ ! -e ~/.jupyter/jupyter_server_config.json ]; then echo '### Run: you have no Jupyter password. Run: make jupyter_password and restart it.'; exit 1; fi"
	# Run notebook in detached mode
	@DOCKER_EXTRA_FLAGS="-d" ./bin/docker.sh uv run jupyter lab --collaborative --ip 0.0.0.0 --no-browser
	# Run copy git credentials for the ingredient editor
	docker cp ~/.gitconfig ${ECOBALYSE_CONTAINER_NAME}:/home/ubuntu/
	@echo "Jupyter started, listening on port ${JUPYTER_PORT}."


stop_notebook:
	@echo "Stopping Jupyter notebook and container..."
	-@./bin/docker.sh bash -c "pkill jupyter" || true
	@docker stop ${ECOBALYSE_CONTAINER_NAME} || echo "Container ${ECOBALYSE_CONTAINER_NAME} not running or already stopped."
	@echo "Container ${ECOBALYSE_CONTAINER_NAME} has been stopped."

start_bwapi:
	echo starting the Brightway API on port 8000...
	@./bin/docker.sh bash -c "cd /home/ecobalyse/ecobalyse-data/bwapi; uv run uvicorn --host 0.0.0.0 server:api"

clean_data:
	docker volume rm ${ECOBALYSE_CONTAINER_NAME}

clean_image:
	docker image rm ${ECOBALYSE_IMAGE_NAME}

clean: clean_data clean_image
