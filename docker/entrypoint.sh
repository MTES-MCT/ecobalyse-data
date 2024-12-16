#!/bin/bash

# Create required directories
gosu ubuntu mkdir -p $BRIGHTWAY2_DIR $BRIGHTWAY2_OUTPUT_DIR $XDG_CACHE_HOME $UV_CACHE_DIR

exec gosu ubuntu "$@"
