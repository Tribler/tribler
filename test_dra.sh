#!/bin/sh -x
#
# We should run the tests in a separate Python interpreter to prevent 
# problems with our singleton classes, e.g. SuperPeerDB, etc.
#
# WARNING: this shell script must use \n as end-of-line, Windows
# \r\n gives problems running this on Linux

python test_dra.py singtest_good_dreply
python test_dra.py singtest_bad_not_bdecodable
python test_dra.py singtest_bad_not_string
python test_dra.py singtest_bad_not_validip
python test_dra.py singtest_bad_diff_ips
python test_dra2.py singtest_good_dreply
python test_dra2.py singtest_bad_not_bdecodable
python test_dra2.py singtest_bad_not_string
python test_dra2.py singtest_bad_not_validip
python test_dra2.py singtest_bad_diff_ips
