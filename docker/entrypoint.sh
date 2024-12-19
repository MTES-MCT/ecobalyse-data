#!/bin/bash

#!/bin/bash
ECOBALYSE_ID=$(ls -lnd /home/ecobalyse/ecobalyse-data|awk '{print $3}')
UBUNTU_ID=$(id -u ubuntu)

if [ $ECOBALYSE_ID -ne $UBUNTU_ID ]; then
    usermod -u $ECOBALYSE_ID ubuntu
fi

chown -R ubuntu:100 "/home/ubuntu"

# Create required directories
gosu ubuntu mkdir -p $BRIGHTWAY2_DIR $BRIGHTWAY2_OUTPUT_DIR $XDG_CACHE_HOME $UV_CACHE_DIR

exec gosu ubuntu "$@"
