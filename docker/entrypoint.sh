#!/bin/bash

gosu ubuntu mkdir -p $BRIGHTWAY2_DIR
gosu ubuntu mkdir -p $BRIGHTWAY2_OUTPUT_DIR

exec gosu ubuntu "$@"
