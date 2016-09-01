#!/bin/bash

set -e

export ADB=/opt/android-sdk/platform-tools/adb

echo Start nosetests
$ADB shell am start -n org.tribler.android/.NoseTestActivity
