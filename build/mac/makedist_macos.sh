#!/usr/bin/env bash
set -x # print all commands
set -e # exit when any command fails

# Script to build Tribler 64-bit on Mac
# Initial author(s): Riccardo Petrocco, Arno Bakker

source ./build/mac/env.sh

# ----- Build
pyinstaller tribler.spec --log-level="${LOG_LEVEL}"

mkdir -p $INSTALL_DIR
mv $DIST_DIR/$APPNAME.app $INSTALL_DIR

# From original Makefile
# Background
mkdir -p $INSTALL_DIR/.background
cp $RESOURCES_DIR/background.png $INSTALL_DIR/.background

# Volume Icon
cp $RESOURCES_DIR/VolumeIcon.icns $INSTALL_DIR/.VolumeIcon.icns

# Shortcut to /Applications
ln -s /Applications $INSTALL_DIR/Applications

touch $INSTALL_DIR

mkdir -p $TEMP_DIR

# Sign the app if environment variables are set
./build/mac/sign_app.sh

# create image
hdiutil create -fs HFS+ -srcfolder $INSTALL_DIR -format UDRW -scrub -volname ${APPNAME} $DIST_DIR/$APPNAME.dmg

# open it
hdiutil attach -readwrite -noverify -noautoopen $DIST_DIR/$APPNAME.dmg -mountpoint $TEMP_DIR/mnt

# make sure root folder is opened when image is
bless --folder $TEMP_DIR/mnt --openfolder $TEMP_DIR/mnt
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
SetFile -a C $TEMP_DIR/mnt || true

# close
hdiutil detach $TEMP_DIR/mnt || true

# make read-only
mv $DIST_DIR/$APPNAME.dmg $TEMP_DIR/rw.dmg
hdiutil convert $TEMP_DIR/rw.dmg -format UDZO -imagekey zlib-level=9 -o $DIST_DIR/$APPNAME.dmg
rm -f $TEMP_DIR/rw.dmg

if [ ! -z "$DMGNAME" ]; then
    mv $DIST_DIR/$APPNAME.dmg $DIST_DIR/$DMGNAME.dmg
fi

# Sign the dmg package and verify it
./build/mac/sign_dmg.sh
