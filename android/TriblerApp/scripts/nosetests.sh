#!/bin/bash

set -e

DEVICE=model:Nexus_6

echo Start nosetests
adb -s $DEVICE shell am start -n org.tribler.android/.NoseTestActivity

echo Waiting on tests to finish
python wait_for_process_death.py "org.tribler.android:service_NoseTestService" $DEVICE

echo Fetching results
python adb_pull.py "nosetests.xml" "" $DEVICE
python adb_pull.py "coverage.xml" "" $DEVICE
