# CODE REVIEW:
# Selects python interpreter based on Unix OS flavor,
# looks for proper Tribler code dir.
# Selects profiler vs regular version of Tribler based on env var
# OBJECTION:
# Do we really have to do it this way? How do other similar projects handle startup on different systems?


#!/bin/sh
# Run Tribler from source tree

UNAME="$(uname -s)"

if [ -z "$PROFILE_TRIBLER" ]; then
    TRIBLER_SCRIPT=run_tribler.py
else
    TRIBLER_SCRIPT=Tribler/Main/tribler_profiler.py
fi

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
    python2.7 $TRIBLER_SCRIPT "$@"
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
        python2.7 $TRIBLER_SCRIPT "$@"
    fi
fi
