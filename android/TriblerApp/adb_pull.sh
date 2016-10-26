#!/bin/bash

set -e

export ADB=/opt/android-sdk/platform-tools/adb

python adb_pull.py -i "/data/data/org.tribler.android/.Tribler/.Tribler/sqlite/tribler.sdb" -o "/home/paul/.Tribler/tribler.sdb"
