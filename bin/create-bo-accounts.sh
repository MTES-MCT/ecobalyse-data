#!/usr/bin/env bash

ROOT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/.." &> /dev/null && pwd )
cd $ROOT_DIR

if [ "$IS_REVIEW_APP" == "true" ]; then
   echo "-> In review app";
   cd backend
   uv run backend database drop-all --no-prompt
   uv run backend database upgrade --no-prompt
   uv run backend users create-user --email vincent.jousse@beta.gouv.fr --name "Vinc Beta" --superuser
   uv run backend users create-user --email vincent@jousse.org --name "Vince Perso" --superuser
   cd ..
fi
