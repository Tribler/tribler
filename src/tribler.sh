#!/bin/sh
# Run Tribler from source tree

script_path() {
  if readlink --help 2>/dev/null | grep -q canonicalize ; then
    # Linux can support following soft links
    FILE="$(readlink -f "$1")"
    echo "${FILE%/*}"
  else
    # MacOS
    DIR="${1%/*}"
    (cd "$DIR" && pwd -P)
  fi
}

UNAME="$(uname -s)"

# Add all required modules to PYTHONPATH
SRC_DIR="$(dirname "$(script_path "$0")")/src"
PYTHONPATH="$PYTHONPATH:$SRC_DIR"
export PYTHONPATH

TRIBLER_SCRIPT=$SRC_DIR/run_tribler.py

PYQTGRAPH_QT_LIB="PyQt5"
export PYQTGRAPH_QT_LIB

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
    python3 "$TRIBLER_SCRIPT" "$@"
elif uname -s | grep -q CYGWIN_NT ; then
    python "$TRIBLER_SCRIPT" "$@"
else
    if [ "$UNAME" = "Darwin" ]; then
        if [ ! -e "$TRIBLER_SCRIPT" ]; then
            echo "ERROR: Script must be called from source tree root"
            echo "  Try the following commands:"
            echo "cd $(dirname "$0")"
            echo "./$(basename "$0")"
            exit 1
        fi
        python3 "$TRIBLER_SCRIPT" "$@"
    fi
fi
