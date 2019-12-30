#!/bin/sh
# Run Tribler from source tree

UNAME="$(uname -s)"

TRIBLER_SCRIPT=run_tribler.py

PYTHONPATH=.:"$PYTHONPATH"
export PYTHONPATH

if [ "$UNAME" = "Linux" ]; then
    # Find the Tribler dir
    TRIBLER_DIR="$(dirname "$(readlink -f "$0")")"
    if [ ! -d "$TRIBLER_DIR" ]; then
        echo "Couldn't figure out where Tribler is, bailing out."
        exit 1
    fi
    cd "$TRIBLER_DIR" || {
        echo "Couldn't cd to $TRIBLER_DIR. Check permissions."
        exit 1
    }
    python3 $TRIBLER_SCRIPT "$@"
elif [ ! -z `uname -s | grep CYGWIN_NT` ]; then
    python $TRIBLER_SCRIPT "$@"
else
    if [ "$UNAME" = "Darwin" ]; then
        if [ ! -e $TRIBLER_SCRIPT ]; then
            echo "ERROR: Script must be called from source tree root"
            echo "  Try the following commands:"
            echo "cd $(dirname $0)"
            echo "./$(basename $0)"
            exit 1
        fi
        python3 $TRIBLER_SCRIPT "$@"
    fi
fi
