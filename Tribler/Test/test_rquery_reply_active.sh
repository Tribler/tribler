#!/bin/sh -x
#
# We should run the tests in a separate Python interpreter to prevent 
# problems with our singleton classes, e.g. SuperPeerDB, etc.
#
# WARNING: this shell script must use \n as end-of-line, Windows
# \r\n gives problems running this on Linux

PYTHONPATH=../..:"$PYTHONPATH"
export PYTHONPATH

python test_rquery_reply_active.py singtest_good_simple_reply
python test_rquery_reply_active.py singtest_good_simpleplustorrents_reply
python test_rquery_reply_active.py singtest_bad_not_bdecodable
python test_rquery_reply_active.py singtest_bad_not_bdecodable_torrentfile
