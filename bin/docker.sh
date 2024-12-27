#!/usr/bin/env bash

# Be sure to exit as soon as something goes wrong
set -eo pipefail

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
ROOT_DIR=$( dirname $SCRIPT_DIR )

IMAGE_NAME="ecobalyse-data"
CONTAINER_NAME="ecobalyse-data"
JUPYTER_PORT="${JUPYTER_PORT:-8888}"
DOCKER_EXTRA_FLAGS="${DOCKER_EXTRA_FLAGS:-}"

if [ -z "$ECOBALYSE_DATA_DIR" ]
then
  echo "🚨 Error: No ECOBALYSE_DATA_DIR in environment. Consider adding it in .env and run: pipenv shell"
  echo "-> Exiting"
  exit 1
fi

if [ -z "$ECOBALYSE_IMAGE_NAME" ]
then
  echo "ℹ️ \$ECOBALYSE_IMAGE_NAME env var not set, using \`$IMAGE_NAME\` as default image name"
else
  IMAGE_NAME=$ECOBALYSE_IMAGE_NAME
fi

if [ -z "$ECOBALYSE_CONTAINER_NAME" ]
then
  echo "ℹ️ \$ECOBALYSE_CONTAINER_NAME env var not set, using \`$CONTAINER_NAME\` as default container name"
else
  CONTAINER_NAME=$ECOBALYSE_CONTAINER_NAME
fi

if [ ! "$(docker ps -a -q -f name=$CONTAINER_NAME)" ]; then

    echo "-> Creating a new container named \`$CONTAINER_NAME\` using image name \`$IMAGE_NAME\`"

    docker run --rm -it $DOCKER_EXTRA_FLAGS\
      -v $CONTAINER_NAME:/home/ubuntu \
      -v $ROOT_DIR:/home/ecobalyse/ecobalyse-data \
      -v $ROOT_DIR/../dbfiles/:/home/ecobalyse/dbfiles \
      -v $ECOBALYSE_DATA_DIR:/home/ecobalyse/ecobalyse-output-dir \
      -e PYTHONPATH=. \
      -e ECOBALYSE_DATA_DIR=/home/ecobalyse/ecobalyse-outpout-dir/ \
      -w /home/ecobalyse/ecobalyse-data/ \
      --name $CONTAINER_NAME \
    $IMAGE_NAME "$@"
else
    echo "-> Using the existing container: \`$CONTAINER_NAME\`"

    docker exec -u ubuntu -it $DOCKER_EXTRA_FLAGS\
      -e ECOBALYSE_DATA_DIR=/home/ecobalyse/ecobalyse-output-dir/ \
      -w /home/ecobalyse/ecobalyse-data \
    $IMAGE_NAME "$@"
fi
