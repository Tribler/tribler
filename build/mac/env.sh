#!/usr/bin/env bash
set -x # print all commands
set -e # exit when any command fails

arch=$(uname -p)
export APPNAME="tribler-$GITHUB_TAG-$arch"
export DMGNAME="tribler-$GITHUB_TAG-$arch"

export LOG_LEVEL=${LOG_LEVEL:-"DEBUG"}
export BUILD_ENV=${BUILD_ENV:-"venv"}

# Directories
export DIST_DIR=dist
export INSTALL_DIR=$DIST_DIR/installdir
export TEMP_DIR=$DIST_DIR/temp
export RESOURCES_DIR=build/mac/resources

# Environment variables related to signing
export CODE_SIGN_ENABLED=${CODE_SIGN_ENABLED:-""}
export APPLE_DEV_ID=${APPLE_DEV_ID:-""}
