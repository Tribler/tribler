#!/usr/bin/env bash
set -x # print all commands
set -e # exit when any command fails

export APPNAME=Tribler
export LOG_LEVEL=${LOG_LEVEL:-"DEBUG"}
export BUILD_ENV=${BUILD_ENV:-"venv"}

PRE_BUILD_INSTRUCTIONS=$(cat <<-END
  git describe --tags | python -c "import sys; print(next(sys.stdin).lstrip('v'))" > .TriblerVersion
  git rev-parse HEAD > .TriblerCommit

  export TRIBLER_VERSION=\$(head -n 1 .TriblerVersion)
  python3 ./build/update_version.py -r .
END
)

if [ ! -f .TriblerVersion ]; then
  echo "No .TriblerVersion file found, run the following commands:"
  echo "$PRE_BUILD_INSTRUCTIONS"
  exit 1
fi

if [ -e .TriblerVersion ]; then
    export DMGNAME="Tribler-$(cat .TriblerVersion)"
fi

# Directories
export DIST_DIR=dist
export INSTALL_DIR=$DIST_DIR/installdir
export TEMP_DIR=$DIST_DIR/temp
export RESOURCES_DIR=build/mac/resources

# Environment variables related to signing
export CODE_SIGN_ENABLED=${CODE_SIGN_ENABLED:-""}
export APPLE_DEV_ID=${APPLE_DEV_ID:-""}
