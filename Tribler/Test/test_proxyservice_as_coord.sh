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

#mkdir /tmp/tmp-test-tribler
#cp ../../../../TestTorrent/Coord1/Gopher.torrent /tmp/Gopher.torrent

python test_proxyservice_as_coord.py singtest_good_proxy
python test_proxyservice_as_coord.py singtest_bad_proxy_ask_for_help
python test_proxyservice_as_coord.py singtest_bad_proxy_metadata_not_bdecodable
python test_proxyservice_as_coord.py singtest_bad_proxy_metadata_not_dict1
python test_proxyservice_as_coord.py singtest_bad_proxy_metadata_not_dict2
python test_proxyservice_as_coord.py singtest_bad_2fast_metadata_empty_dict
python test_proxyservice_as_coord.py singtest_bad_proxy_metadata_wrong_dict_keys
python test_proxyservice_as_coord.py singtest_bad_proxy_metadata_bad_torrent1
python test_proxyservice_as_coord.py singtest_bad_proxy_metadata_bad_torrent2
python test_proxyservice_as_coord.py singtest_bad_proxy_metadata_bad_torrent3
