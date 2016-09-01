#!/bin/bash

set -e

export ADB=/opt/android-sdk/platform-tools/adb

echo Start experiment
$ADB shell am start -n org.tribler.android/.ExperimentActivity --es "experiment" "ExperimentMultiChainScale" --ei "blocks_in_thousands" 10
