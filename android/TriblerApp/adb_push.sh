#!/bin/bash

set -e

export ADB=/opt/android-sdk/platform-tools/adb

python adb_push.py "tribler.sdb" "../.Tribler/.Tribler/sqlite/tribler.sdb"
