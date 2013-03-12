#!/bin/sh
# Startup script for Ubuntu Linux

_TRIBLERPATH="/usr/share/tribler"

export PYTHONPATH="$PYTHONPATH":$_TRIBLERPATH

echo "Starting Tribler..."
cd $_TRIBLERPATH
exec python -O Tribler/Main/tribler.py "$@" > /tmp/$USER-tribler.log 2>&1
