#!/bin/sh -x
#
# We should run the tests in a separate Python interpreter to prevent 
# problems with our singleton classes, e.g. SuperPeerDB, etc.
#
# WARNING: this shell script must use \n as end-of-line, Windows
# \r\n gives problems running this on Linux

python test_qra.py singtest_good_qreply
python test_qra.py singtest_bad_not_bdecodable
