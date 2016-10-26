#!/bin/bash

set -e

export ADB=/opt/android-sdk/platform-tools/adb

echo Start experiment
$ADB shell am start -n org.tribler.android/.ExperimentActivity -e "experiment" "ExperimentMultiChainScale" -e "blocks_in_thousands" 2
