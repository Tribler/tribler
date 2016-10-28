#!/bin/bash

set -e

export ADB="adb -s $DEVICE"

timestamp=$(date +%s)

echo Uninstall
$ADB uninstall org.tribler.android

echo Remove appstate
$ADB shell rm -rf /sdcard/.Tribler

echo Install
$ADB install ../app/build/outputs/apk/app-debug.apk

echo Default appstate
$ADB push /home/paul/Tribler_appstate/fav_only_tpb/.Tribler /sdcard/.Tribler/.Tribler
