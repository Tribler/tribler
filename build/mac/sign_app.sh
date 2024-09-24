#!/bin/bash
set -x # print all commands
set -e # exit when any command fails

source ./build/mac/env.sh

# App file to sign
APP_FILE=$INSTALL_DIR/$APPNAME.app
if [ -z "$APP_FILE" ]; then
    echo "$APP_FILE file not found"
    exit 1
fi

if [ -z "$CODE_SIGN_ENABLED" ]; then
    echo "Code sign is not enabled. Skipping code signing the app $APP_FILE."
    exit 0
fi

if [ -z "$APPLE_DEV_ID" ]; then
    echo "Code sign is enabled but Apple Dev ID is not set. Exiting with failure"
    exit 1
fi

echo "Signing $APP_FILE with Apple Dev ID: $APPLE_DEV_ID"
SIGN_MSG="Developer ID Application: $APPLE_DEV_ID"
codesign --deep --force --verbose --sign "$SIGN_MSG" --entitlements ./build/mac/entitlements.plist --options runtime $APP_FILE
