#!/bin/sh
# Run Tribler from source tree


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

if [ ! -e Tribler/Main/tribler.py ]
then
	echo "ERROR: Script must be called from source tree root"
	echo "  Try the following commands:"
	echo "cd $(dirname $0)"
	echo "./$(basename $0)"
	exit 1
fi

python Tribler/Main/tribler.py
