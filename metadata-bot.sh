#!/bin/bash

# Find the Tribler dir
TRIBLER_DIR=$( dirname $(readlink -f "$0"))
if [ ! -d "$TRIBLER_DIR" ]; then
    TRIBLER_DIR=$( dirname $(readlink -f $(which "$0")))
fi
if [ ! -d "$TRIBLER_DIR" ]; then
    echo "Couldn't figure out where Tribler is, bailing out."
    exit 1
fi

cd $TRIBLER_DIR

PYTHONPATH=.:"$PYTHONPATH"
export PYTHONPATH

python Tribler/Main/metadata-injector.py $@

