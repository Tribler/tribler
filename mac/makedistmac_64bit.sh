#!/bin/sh -xe
#
# Written by Riccardo Petrocco, Arno Bakker
# see LICENSE.txt for license information
#
# Script to build Tribler 64-bit on Mac
#
# Based on original Makefile by JD Mol.

APPNAME=Tribler
if [ -e .TriblerVersion ]; then
    DMGNAME="Tribler-$(cat .TriblerVersion)"
fi

export LIBRARYNAME=Tribler

PYTHON_VERSION=2.7
PYTHON="/System/Library/Frameworks/Python.framework/Versions/$PYTHON_VERSION/bin/python$PYTHON_VERSION"

# ----- Set python paths TODO dynamic checkout

PYTHONPATH="$PWD:$PYTHONPATH"
PYTHONPATH="$HOME/Workspace_new/install/lib/python2.7/site-packages:$PYTHONPATH"
PYTHONPATH="/Users/tribler/Library/Python/2.7/lib/python/site-packages/:$PYTHONPATH" # user-defined libraries
export PYTHONPATH

# ----- Clean up
/bin/rm -rf dist build

# ----- Build
${PYTHON} -OO - < ${LIBRARYNAME}/Main/Build/Mac/setuptriblermac_64bit.py py2app

mkdir -p dist/installdir
mv dist/$APPNAME.app dist/installdir

# From original Makefile
# Background
mkdir -p dist/installdir/.background
cp $LIBRARYNAME/Main/Build/Mac/background.png dist/installdir/.background

# Volume Icon
cp $LIBRARYNAME/Main/Build/Mac/VolumeIcon.icns dist/installdir/.VolumeIcon.icns

# Shortcut to /Applications
ln -s /Applications dist/installdir/Applications

touch dist/installdir

#Copy logger.conf
cp logger.conf dist/installdir/Tribler.app/Contents/Resources/

# Copy family filter
cp Tribler/Category/category.conf dist/installdir/Tribler.app/Contents/Resources/Tribler/Category/
cp Tribler/Category/filter_terms.filter dist/installdir/Tribler.app/Contents/Resources/Tribler/Category/

mkdir -p dist/temp

# create image
hdiutil create -srcfolder dist/installdir -format UDRW -scrub -volname ${APPNAME} dist/$APPNAME.dmg

# open it
hdiutil attach -readwrite -noverify -noautoopen dist/$APPNAME.dmg -mountpoint dist/temp/mnt

# make sure root folder is opened when image is
bless --folder dist/temp/mnt --openfolder dist/temp/mnt
# hack: wait for completion
sleep 1

# Arno, 2011-05-15: Snow Leopard gives diff behaviour, so set initial 1000 bounds to normal size
# and added close/open after set position, following
# http://stackoverflow.com/questions/96882/how-do-i-create-a-nice-looking-dmg-for-mac-os-x-using-command-line-tools

# position items
# oddly enough, 'set f .. as alias' can fail, but a reboot fixes that
osascript -e "tell application \"Finder\"" \
-e "   set f to POSIX file (\"${PWD}/dist/temp/mnt\" as string) as alias" \
-e "   tell folder f" \
-e "       open" \
-e "       tell container window" \
-e "          set toolbar visible to false" \
-e "          set statusbar visible to false" \
-e "          set current view to icon view" \
-e "          delay 1 -- Sync" \
-e "          set the bounds to {50, 100, 600, 400} -- Big size so the finder won't do silly things" \
-e "       end tell" \
-e "       delay 1 -- Sync" \
-e "       set icon size of the icon view options of container window to 128" \
-e "       set arrangement of the icon view options of container window to not arranged" \
-e "       set background picture of the icon view options of container window to file \".background:background.png\"" \
-e "       set position of item \"${APPNAME}.app\" to {150, 140}" \
-e "       set position of item \"Applications\" to {410, 140}" \
-e "       set the bounds of the container window to {50, 100, 600, 400}" \
-e "       close" \
-e "       open" \
-e "       update without registering applications" \
-e "       delay 5 -- Sync" \
-e "       close" \
-e "   end tell" \
-e "   -- Sync" \
-e "   delay 5" \
-e "end tell" || true

# turn on custom volume icon
SetFile -a C dist/temp/mnt || true

# close
hdiutil detach dist/temp/mnt || true

# make read-only
mv dist/$APPNAME.dmg dist/temp/rw.dmg
hdiutil convert dist/temp/rw.dmg -format UDZO -imagekey zlib-level=9 -o dist/$APPNAME.dmg
rm -f dist/temp/rw.dmg

# add EULA
eulagise --license $LIBRARYNAME/LICENSE.txt --target dist/$APPNAME.dmg

if [ ! -z "$DMGNAME" ]; then
    mv dist/$APPNAME.dmg dist/$DMGNAME.dmg
fi
