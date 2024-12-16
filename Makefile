SHELL := /bin/bash
NAME := ecobalyse-data
ECOBALYSE_DATA_DIR := ${ECOBALYSE_DATA_DIR}
JUPYTER_PORT ?= 8888

# Define a DOCKER function
define DOCKER
env | grep ECOBALYSE_DATA_DIR || echo "No ECOBALYSE_DATA_DIR in environment. Consider adding it in .env and run: pipenv shell"
env | grep ECOBALYSE_DATA_DIR || exit
@if [ "$(shell docker container inspect -f '{{.State.Running}}' $(NAME) )" = "true" ]; then \
  echo "(Using the existing container)" &&\
	docker exec -u ecobalyse -it -e ECOBALYSE_DATA_DIR=/home/ecobalyse/ecobalyse-private/ -w /home/ecobalyse/ecobalyse-data $(NAME) $(1);\
else \
	echo "(Creating a new container)" &&\
  docker run --rm -it -v $$PWD/:/home/ecobalyse/ecobalyse-data -v $$PWD/../dbfiles/:/home/ecobalyse/dbfiles -v $(ECOBALYSE_DATA_DIR):/home/ecobalyse/ecobalyse-private -e ECOBALYSE_DATA_DIR=/home/ecobalyse/ecobalyse-private/ -w /home/ecobalyse/ecobalyse-data/ $(NAME) $(1); fi
endef

all: import export
import : image import_food import_ecoinvent import_method create_activities sync_datapackages
export: export_food export_textile export_object format

image:
	docker build -t $(NAME) -f docker/Dockerfile .

import_food:
	@$(call DOCKER,uv run python import_food.py)

import_method:
	@$(call DOCKER,uv run python import_method.py)

import_ecoinvent:
	@$(call DOCKER,uv run python import_ecoinvent.py)

create_activities:
	@$(call DOCKER,uv run python create_activities.py)

sync_datapackages:
	@$(call DOCKER,uv run python common/sync_datapackages.py)

delete_database:
	@$(call DOCKER,uv run python common/delete_database.py $(DB))

delete_method:
	@$(call DOCKER,uv run python common/delete_methods.py)

export_food:
	@$(call DOCKER,uv run python food/export.py)

export_textile:
	@$(call DOCKER,uv run python textile/export.py)

export_object:
	@$(call DOCKER,uv run python object/export.py)

compare_food:
	@$(call DOCKER,uv run python food/export.py compare)

compare_textile:
	@$(call DOCKER,uv run python textile/export.py compare)

format:
	npm run fix:all

python:
	echo Running Python inside the container...
	@$(call DOCKER,uv run python)

shell:
	echo starting a user shell inside the container...
	@$(call DOCKER,bash)

jupyter_password:
	echo starting a user shell inside the container...
	@$(call DOCKER,uv run jupyter notebook password)

start_notebook:
	docker run --rm -it \
    -v $(NAME):/home/jovyan \
    -v $$PWD/../dbfiles:/home/jovyan/dbfiles \
    -v $$PWD:/home/jovyan/ecobalyse \
    -v $(ECOBALYSE_DATA_DIR):/home/jovyan/ecobalyse-private \
    -e ECOBALYSE_DATA_DIR=/home/jovyan/ecobalyse-private/ \
    -e JUPYTER_PORT=$(JUPYTER_PORT) \
    -e JUPYTER_ENABLE_LAB=yes \
    -p $(JUPYTER_PORT):$(JUPYTER_PORT) \
    --name $(NAME) \
    $(NAME) start-notebook.sh --collaborative
	docker cp ~/.gitconfig $(NAME):/home/jovyan/
	docker exec -it -u jovyan $(NAME) \
	   bash -c "if [ ! -e ~/.jupyter/jupyter_server_config.json ]; then echo '### Run: you have no Jupyter password. Run: make jupyter_password and restart it.'; fi"

stop_notebook:
	@echo "Stopping Jupyter notebook and container..."
	-@$(call DOCKER,bash -c "pkill jupyter") || true
	-docker stop $(NAME) || echo "Container $(NAME) not running or already stopped."
	@echo "Container $(NAME) has been stopped."

start_bwapi:
	echo starting the Brightway API on port 8000...
	@$(call DOCKER,bash -c "cd /home/jovyan/ecobalyse/data/bwapi; uvicorn --host 0.0.0.0 server:api")

clean_data:
	docker volume rm $(NAME)

clean_image:
	docker image rm $(NAME)

clean: clean_data clean_image
