#!/bin/bash

set -e

export ADB=/opt/android-sdk/platform-tools/adb

echo Make screenshot, saving to screen.png...
$ADB shell screencap -p | sed 's/\r$//' > screen.png
