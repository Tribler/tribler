#!/bin/bash

set -e

export ADB="adb -s $DEVICE"

timestamp=$(date +%s)

$ADB logcat -c

echo Start twistd
$ADB shell am start -n org.tribler.android/.TwistdActivity
