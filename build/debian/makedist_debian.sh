#!/bin/sh
# Script to build Tribler Debian package.
# Note: Run the script from root directory, eg.
# /build/debian/makedist_debian.sh

rm -rf build/tribler
rm -rf dist/tribler
rm -rf build/debian/tribler/usr/share/tribler

python3 build/update_version_from_git.py

python3 -m PyInstaller tribler.spec

cp -r dist/tribler build/debian/tribler/usr/share/tribler

sed -i "s/__VERSION__/$(cat .TriblerVersion)/g" build/debian/tribler/DEBIAN/control
dpkg-deb -b build/debian/tribler tribler_$(cat .TriblerVersion)_all.deb