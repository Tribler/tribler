#!/bin/sh -x
#
# Written by George Milescu
# see LICENSE.txt for license information
#
# We should run the tests in a separate Python interpreter to prevent 
# problems with our singleton classes, e.g. SuperPeerDB, etc.
#
# WARNING: this shell script must use \n as end-of-line, Windows
# \r\n gives problems running this on Linux

PYTHONPATH=../..:"$PYTHONPATH"
export PYTHONPATH

python test_proxyservice.py singtest_good_2fast
#python test_proxyservice.py singtest_bad_2fast_dlhelp
#python test_proxyservice.py singtest_bad_2fast_metadata_not_bdecodable
#python test_proxyservice.py singtest_bad_2fast_metadata_not_dict1
#python test_proxyservice.py singtest_bad_2fast_metadata_not_dict2
#python test_proxyservice.py singtest_bad_2fast_metadata_empty_dict
#python test_proxyservice.py singtest_bad_2fast_metadata_wrong_dict_keys
#python test_proxyservice.py singtest_bad_2fast_metadata_bad_torrent1
#python test_proxyservice.py singtest_bad_2fast_metadata_bad_torrent2
#python test_proxyservice.py singtest_bad_2fast_metadata_bad_torrent3
