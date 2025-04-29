#!/usr/bin/env bash

ROOT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/.." &> /dev/null && pwd )
cd $ROOT_DIR

if [ "$IS_REVIEW_APP" == "true" ]; then
   echo "-> In review app";
   cd backend
   uv run backend database drop-all --no-prompt
   uv run backend database upgrade --no-prompt
   cd ..
fi
