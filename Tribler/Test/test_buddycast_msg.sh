#!/bin/sh -x
#
# We should run the tests in a separate Python interpreter to prevent 
# problems with our singleton classes, e.g. SuperPeerDB, etc.
#
# WARNING: this shell script must use \n as end-of-line, Windows
# \r\n gives problems running this on Linux

PYTHONPATH=../..:"$PYTHONPATH"
export PYTHONPATH

python test_buddycast_msg.py singtest_good_buddycast2
python test_buddycast_msg.py singtest_good_buddycast3
python test_buddycast_msg.py singtest_good_buddycast4
python test_buddycast_msg.py singtest_good_buddycast6
python test_buddycast_msg.py singtest_bad_all
