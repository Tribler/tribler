#!/bin/bash

export ADB=/opt/android-sdk-linux/platform-tools/adb

echo Make screenshot, saving to screen.png...
$ADB shell screencap -p | sed 's/\r$//' > screen.png
