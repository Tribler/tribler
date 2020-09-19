script_path() {
  DIR="${1%/*}"
  (cd "$DIR" && echo "$(pwd -P)")
}

SRC_DIR="$(dirname "$(script_path "$0")")/src"
export PYTHONPATH=$SRC_DIR/tribler-core:$SRC_DIR/tribler-common
pytest $SRC_DIR/tribler-core "$@"
