#!/bin/bash
set -x # print all commands
set -e # exit when any command fails

source ./build/mac/env.sh

DMG_FILE=$DIST_DIR/$DMGNAME.dmg
if [ -z "$DMG_FILE" ]; then
    echo "$DMG_FILE file not found"
    exit 1
fi

if [ -z "$CODE_SIGN_ENABLED" ]; then
    echo "Code sign is not enabled. Skipping code signing the installer $DMG_FILE."
    exit 0
fi

if [ -z "$APPLE_DEV_ID" ]; then
    echo "Code sign is enabled but Apple Dev ID is not set. Exiting with failure"
    exit 1
fi

# Sign the dmg package and verify it
SIGN_MSG="Developer ID Application: $APPLE_DEV_ID"
codesign --force --verify --verbose --sign "$SIGN_MSG" $DMG_FILE
codesign --verify --verbose=4 $DMG_FILE

# Assuming the keychain profile with the signing key is created and named as "tribler-codesign-profile".
# If not create the keychain profile with the following command:
# xcrun notarytool store-credentials "tribler-codesign-profile" --apple-id "<dev-id-email>" --team-id "<dev-id-team>"
KEYCHAIN_PROFILE=${KEYCHAIN_PROFILE:-"tribler-codesign-profile"}
# Submit the DMG for notarization and staple afterwards
xcrun notarytool submit $DMG_FILE --keychain-profile "$KEYCHAIN_PROFILE" --wait
xcrun stapler staple $DMG_FILE
# Verify the notarization
spctl --assess --type open --context context:primary-signature -v $DMG_FILE
