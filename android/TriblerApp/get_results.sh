#!/bin/bash

set -e

export ADB=/opt/android-sdk/platform-tools/adb

echo Get experiment results
$ADB root
$ADB pull "/data/data/org.tribler.android/files/ExperimentMultiChainScale.dat"
