#!/bin/bash

#export DEVICE=model:Nexus_10

#export ADB="adb -s $DEVICE"

timestamp=$(date +%s)

#./uninstall.sh

#./install.sh
#./install_grant.sh

#./default_appstate.sh

$ADB root

echo Clean logcat
$ADB logcat -c

./start_app.sh

python startup_time.py "startup.$DEVICE.[#2599].dat"

./stop_app.sh

python shutdown_time.py "shutdown.$DEVICE.[#2599].dat"
