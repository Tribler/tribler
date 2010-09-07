REM
REM Written by George Milescu
REM see LICENSE.txt for license information
REM
REM We should run the tests in a separate Python interpreter to prevent 
REM problems with our singleton classes, e.g. SuperPeerDB, etc.
REM

set PYTHONPATH=..\..

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
