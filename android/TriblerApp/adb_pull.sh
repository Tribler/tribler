#!/bin/bash

set -e

export ADB=/opt/android-sdk/platform-tools/adb

python adb_pull.py "../.Tribler/.Tribler/sqlite/tribler.sdb"
