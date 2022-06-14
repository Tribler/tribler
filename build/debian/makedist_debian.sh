#!/usr/bin/env bash
set -x # print all commands
set -e # exit when any command fails

LOG_LEVEL=${LOG_LEVEL:-"DEBUG"}

if [[ ! -d build/debian ]]; then
  echo "Please run this script from project root as:\n./build/debian/makedist_debian.sh"
fi

rm -rf build/tribler
rm -rf dist/tribler
rm -rf build/debian/tribler/usr/share/tribler

if [ ! -z "$VENV" ]; then
  echo "Setting venv to $VENV"
  source $VENV/bin/activate
else
  echo "Creating a new venv"
  python3 -m venv build-env
  . ./build-env/bin/activate
fi

# ----- Install dependencies before the build
python3 -m pip install --upgrade pip
python3 -m pip install --upgrade -r requirements-build.txt

# ----- Update version
python3 ./build/update_version.py -r .
python3 ./build/debian/update_metainfo.py -r .

# ----- Build binaries
python3 -m PyInstaller tribler.spec --log-level="${LOG_LEVEL}"

# ----- Build dpkg
cp -r ./dist/tribler ./build/debian/tribler/usr/share/tribler

TRIBLER_VERSION=$(head -n 1 .TriblerVersion) # read the first line only

# Compose the changelog
cd ./build/debian/tribler

dch -v $TRIBLER_VERSION "New release"
dch -v $TRIBLER_VERSION "See https://github.com/Tribler/tribler/releases/tag/$TRIBLER_VERSION for more info"

dpkg-buildpackage -b -rfakeroot -us -uc
