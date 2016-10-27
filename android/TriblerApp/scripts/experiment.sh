#!/bin/bash

set -e

DEVICE=model:Nexus_6

echo Start experiment
adb -s $DEVICE shell am start -n org.tribler.android/.ExperimentActivity --es "experiment" "ExperimentMultiChainScale" --ei "blocks_in_thousands" 10

echo Waiting on experiment to finish
python wait_for_process_death.py "org.tribler.android:service_ExperimentService" $DEVICE

echo Fetching results
python adb_pull.py "ExperimentMultiChainScale.dat" "" $DEVICE
