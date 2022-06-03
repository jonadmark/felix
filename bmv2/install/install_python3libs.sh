#!/bin/bash

# Print commands and exit on errors.
set -xe

conda config --set changeps1 False
conda install -y -c conda-forge jupyterlab
conda install -y networkx scapy numpy pandas matplotlib docopt