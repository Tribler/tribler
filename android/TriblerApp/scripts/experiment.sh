#!/bin/bash

set -e

export ADB="adb -s $DEVICE"

timestamp=$(date +%s)

echo Start experiment
$ADB shell am start -n org.tribler.android/.ExperimentActivity --es "experiment" "ExperimentMultiChainScale" --ei "blocks_in_thousands" 10

echo Waiting on experiment to finish
python wait_for_process_death.py "org.tribler.android:service_ExperimentService"

echo Fetching results
python adb_pull.py "ExperimentMultiChainScale.dat" "$DEVICE.$timestamp.ExperimentMultiChainScale.dat"
