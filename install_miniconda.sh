#!/bin/bash

wget https://repo.anaconda.com/miniconda/Miniconda3-py39_4.11.0-Linux-x86_64.sh -O $HOME/miniconda.sh
chmod +x $HOME/miniconda.sh
$HOME/miniconda.sh -b -p /workspace/miniconda
/workspace/miniconda/condabin/conda init bash
