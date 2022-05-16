#!/bin/bash
# Script to build Tribler Debian package.
# Note: Run the script from root directory, eg.
# ./build/debian/makedist_debian.sh

if [[ ! -d build/debian ]]
then
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
python3 build/update_version_from_git.py

# ----- Build
python3 -m PyInstaller tribler.spec --log-level=DEBUG

cp -r dist/tribler build/debian/tribler/usr/share/tribler

TRIBLER_VERSION=$(cat .TriblerVersion)

pushd build/debian/tribler || exit
# Compose the changelog
dch -v $TRIBLER_VERSION "New release"
dch -v $TRIBLER_VERSION "See https://github.com/Tribler/tribler/releases/tag/$TRIBLER_VERSION for more info"
# Build the package afterwards
dpkg-buildpackage -b -rfakeroot -us -uc
popd || exit
