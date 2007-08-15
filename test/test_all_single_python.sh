#!/bin/sh -x
#
# WARNING: this shell script must use \n as end-of-line, Windows
# \r\n gives problems running this on Linux

PYTHONPATH=..:"$PYTHONPATH"
export PYTHONPATH

python test_all_single_python.py

