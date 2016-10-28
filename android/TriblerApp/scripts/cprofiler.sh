#!/bin/bash

set -e

export ADB="adb -s $DEVICE"

timestamp=$(date +%s)

echo Start twistd
$ADB shell am start -n org.tribler.android/.TwistdActivity
