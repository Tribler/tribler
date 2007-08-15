#!/bin/sh -x
#
# We should run the tests in a separate Python interpreter to prevent 
# problems with our singleton classes, e.g. SuperPeerDB, etc.
#
# WARNING: this shell script must use \n as end-of-line, Windows
# \r\n gives problems running this on Linux

PYTHONPATH=..:"$PYTHONPATH"
export PYTHONPATH
python test_secure_overlay.py singtest_connect_dns_to_dead_peer
python test_secure_overlay.py singtest_connect_dns_to_live_peer
python test_secure_overlay.py singtest_connect_to_dead_peerA
python test_secure_overlay.py singtest_connect_to_dead_peerB
python test_secure_overlay.py singtest_connect_to_live_peer
python test_secure_overlay.py singtest_connect_twice_to_live_peer
python test_secure_overlay.py singtest_send_unopenedA
python test_secure_overlay.py singtest_send_unopenedB
python test_secure_overlay.py singtest_send_local_close
python test_secure_overlay.py singtest_send_remote_close
python test_secure_overlay.py singtest_send_opened
python test_secure_overlay.py singtest_close_unopened
python test_secure_overlay.py singtest_close_opened
python test_secure_overlay.py singtest_receive
python test_secure_overlay.py singtest_got_conn_incoming
python test_secure_overlay.py singtest_got_conn_outgoing
python test_secure_overlay.py singtest_got_conn_local_close
python test_secure_overlay.py singtest_got_conn_remote_close

