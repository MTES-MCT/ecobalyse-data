#!/usr/bin/env bash

# Be sure to exit as soon as something goes wrong
set -eo pipefail

SCRIPT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )" &> /dev/null && pwd )
ROOT_DIR=$( dirname $SCRIPT_DIR )

IMAGE_NAME="ecobalyse-data"
CONTAINER_NAME="ecobalyse-data"
JUPYTER_PORT="${JUPYTER_PORT:-8888}"
DOCKER_EXTRA_FLAGS="${DOCKER_EXTRA_FLAGS:-}"

if [ -z "$EB_OUTPUT_DIR" ]
then
  echo "🚨 Error: No EB_OUTPUT_DIR in environment. Consider adding it in .env and run: pipenv shell"
  echo "-> Exiting"
  exit 1
else
  echo "ℹ️ Using $EB_OUTPUT_DIR as ouput dir."
fi

if [ -z "$EB_IMAGE_NAME" ]
then
  echo "ℹ️ \$EB_IMAGE_NAME env var not set, using \`$IMAGE_NAME\` as default image name"
else
  IMAGE_NAME=$EB_IMAGE_NAME
fi

if [ -z "$EB_CONTAINER_NAME" ]
then
  echo "ℹ️ \$EB_CONTAINER_NAME env var not set, using \`$CONTAINER_NAME\` as default container name"
else
  CONTAINER_NAME=$EB_CONTAINER_NAME
fi

if [ ! "$(docker ps -a -q -f name=$CONTAINER_NAME)" ]; then

    echo "-> Creating a new container named \`$CONTAINER_NAME\` using image name \`$IMAGE_NAME\`"

    docker run --rm -it $DOCKER_EXTRA_FLAGS\
      -v $CONTAINER_NAME:/home/ubuntu \
      -v $ROOT_DIR:/home/eb/ebd \
      -v $ROOT_DIR/../dbfiles/:/home/ecobalyse/dbfiles \
      -v $EB_OUTPUT_DIR:/home/ecobalyse/ecobalyse-output-dir \
      -e EB_OUTPUT_DIR=/home/ecobalyse/ecobalyse-output-dir/ \
      -w /home/ecobalyse/ecobalyse-data/ \
      --name $CONTAINER_NAME \
    $IMAGE_NAME "$@"
else
    echo "-> Using the existing container: \`$CONTAINER_NAME\`"

    docker exec -u ubuntu -it $DOCKER_EXTRA_FLAGS\
      -e EB_OUTPUT_DIR=/home/ecobalyse/ecobalyse-output-dir/ \
      -w /home/ecobalyse/ecobalyse-data \
    $IMAGE_NAME "$@"
fi
