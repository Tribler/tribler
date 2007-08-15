set PYTHONPATH=..

python test_dch.py singtest_connect_dns_to_dead_peer
python test_dch.py singtest_connect_dns_to_live_peer
python test_dch.py singtest_send_unopenedA
python test_dch.py singtest_send_local_close
python test_dch.py singtest_send_remote_close
python test_dch.py singtest_send_opened
python test_dch.py singtest_close_unopened
python test_dch.py singtest_close_opened
python test_dch.py singtest_receive
python test_dch.py singtest_got_conn_incoming
python test_dch.py singtest_got_conn_outgoing
python test_dch.py singtest_got_conn_local_close
python test_dch.py singtest_got_conn_remote_close
