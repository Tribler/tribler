#!/bin/sh
# Run Tribler from source tree

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

python Tribler/AnonTunnel/Main.py --start

