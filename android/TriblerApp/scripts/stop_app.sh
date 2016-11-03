#!/bin/bash

echo Stop app
$ADB shell am start -n org.tribler.android/.MainActivity -a android.intent.action.ACTION_SHUTDOWN

echo Waiting on service to shutdown
python wait_for_process_death.py "org.tribler.android:service_TriblerdService"
