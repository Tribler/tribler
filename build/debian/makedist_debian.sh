#!/bin/bash
# Script to build Tribler Debian package.
# Note: Run the script from root directory, eg.
# ./build/debian/makedist_debian.sh

if [[ ! -d build/debian ]]
then
  echo "Please run this script from project root as:\n./build/debian/makedist_debian.sh"
fi

if [ ! -z "$VENV" ]; then
  echo "Setting venv to $VENV"
  source $VENV/bin/activate
fi

rm -rf build/tribler
rm -rf dist/tribler
rm -rf build/debian/tribler/usr/share/tribler

python3 build/update_version_from_git.py

python3 -m PyInstaller tribler.spec

cp -r dist/tribler build/debian/tribler/usr/share/tribler

TRIBLER_VERSION=$(cat .TriblerVersion)
sed -i "s/__VERSION__/$TRIBLER_VERSION/g" build/debian/snap/snapcraft.yaml

pushd build/debian/tribler || exit
# Compose the changelog using git commits
git log "$(git describe --tags --abbrev=0)"..HEAD --oneline |
while IFS= read -r commit; do
  dch -v $TRIBLER_VERSION "$commit"
done
# Build the package afterwards
dpkg-buildpackage -b -rfakeroot -us -uc
popd || exit

# Build Tribler snap if $BUILD_TRIBLER_SNAP
if [ "$BUILD_TRIBLER_SNAP" == "false" ]; then
  exit 0
fi

# Build snap with docker if exists
if [ -x "$(command -v docker)" ]; then
    echo "Running snapcraft in docker"
    cd build/debian && docker run -v "$PWD":/debian -w /debian triblertester/snap_builder:core18 /bin/bash ./build-snap.sh
else
    cd build/debian && /bin/bash ./build-snap.sh
fi
