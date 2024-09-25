#!/usr/bin/env bash
set -x # print all commands
set -e # exit when any command fails

rm -rf build/tribler
rm -rf dist/tribler
rm -rf build/debian/tribler/usr/share/tribler

# ----- Install dependencies before the build
python3 -m pip install --upgrade PyGObject

# ----- Update version
python3 ./build/debian/update_metainfo.py

# ----- Build binaries
python3 build/setup.py build

# ----- Build dpkg
cp -r ./dist/tribler ./build/debian/tribler/usr/share/tribler

# Compose the changelog
cd ./build/debian/tribler

export DEBEMAIL="info@tribler.org"
export DEBFULLNAME="Tribler"
dch -v $GITHUB_TAG "New release"
dch -v $GITHUB_TAG "See https://github.com/Tribler/tribler/releases/tag/v$GITHUB_TAG for more info"

dpkg-buildpackage -b -rfakeroot -us -uc
