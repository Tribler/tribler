#!/bin/sh -x
#
# We should run the tests in a separate Python interpreter to prevent 
# problems with our singleton classes, e.g. SuperPeerDB, etc.
#
# WARNING: this shell script must use \n as end-of-line, Windows
# \r\n gives problems running this on Linux

PYTHONPATH=../..:"$PYTHONPATH"
export PYTHONPATH

python test_merkle_msg.py singtest_good_hashpiece_bepstyle
python test_merkle_msg.py singtest_good_hashpiece_oldstyle
python test_merkle_msg.py singtest_good_request_bepstyle
python test_merkle_msg.py singtest_bad_hashpiece_bepstyle
python test_merkle_msg.py singtest_bad_hashpiece_oldstyle
