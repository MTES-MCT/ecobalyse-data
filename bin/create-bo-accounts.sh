#!/usr/bin/env bash

ROOT_DIR=$( cd -- "$( dirname -- "${BASH_SOURCE[0]}" )/.." &> /dev/null && pwd )
cd $ROOT_DIR

if [ "$IS_REVIEW_APP" == "true" ]; then
   echo "-> In review app, resetting DB";
   cd backend
   uv run backend database drop-all --no-prompt
   uv run backend database upgrade --no-prompt
   # Test if variable is set
   if test -n "${BACKEND_ADMINS:+x}"; then
     IFS=',' read -ra ADDR <<< "$BACKEND_ADMINS"
     for email in "${ADDR[@]}"; do
       uv run backend users create-user --email $email --superuser
     done
   fi
   cd ..
fi
