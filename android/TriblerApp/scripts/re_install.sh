#!/bin/bash

set -e

export ADB="adb -s $DEVICE"

timestamp=$(date +%s)

echo Uninstall
$ADB uninstall org.tribler.android

echo Install
$ADB install ../app/build/outputs/apk/app-debug.apk
