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

python3 build/update_version_from_git.py

python3 -m PyInstaller tribler.spec

cp -r dist/tribler build/debian/tribler/usr/share/tribler

sed -i "s/__VERSION__/$(cat .TriblerVersion)/g" build/debian/tribler/DEBIAN/control
sed -i "s/__VERSION__/$(cat .TriblerVersion)/g" build/debian/snap/snapcraft.yaml

dpkg-deb -b build/debian/tribler tribler_$(cat .TriblerVersion)_all.deb

# Build snap with docker if exists
if [ -x "$(command -v docker)" ]; then
    echo "Running snapcraft in docker"
    cd build/debian && docker run -v "$PWD":/debian -w /debian triblertester/snap_builder:core18 /bin/bash ./build-snap.sh
else
    cd build/debian && /bin/bash ./build-snap.sh
fi