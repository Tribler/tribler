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

# Allow multiple instances of Tribler to run in development mode.
is_dev_mode=$(echo "$DEV_MODE" | tr '[:upper:]' '[:lower:]') # Convert to lowercase using tr
if [ "$is_dev_mode" = "true" ]; then
  echo "Running Tribler in development mode"
  # Set the state directory
  TSTATEDIR="$HOME/.Tribler"

  # If there are multiple instances of the script running, append a number to the state directory
  script_name=$(basename "$0")  # Get the name of the script
  # Count the instances of the script running, excluding the pgrep command itself
  instance_count=$(pgrep -f "$script_name" | grep -v "$$" | wc -l)
  if [ "$instance_count" -gt 1 ]; then
      TSTATEDIR="$TSTATEDIR-$((instance_count-1))"
  fi
  export TSTATEDIR
  echo "Running Tribler from state directory $TSTATEDIR"
fi

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
