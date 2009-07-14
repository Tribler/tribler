#!/bin/sh
#
# WARNING: this shell script must use \n as end-of-line, Windows
# \r\n gives problems running this on Linux

export PYTHONPATH=../..:"$PYTHONPATH"

python test_sqlitecachedb.py
# python test_friend.py # Arno, 2008-10-17: need to convert to new DB structure
# python test_bsddb2sqlite.py # Arno, 2008-11-26: Alea jacta est.
python test_superpeers.py 
# python test_buddycast.py # currently not working due to missing DataHandler functions, 2008-10-17
# python test_sim.py # currently not working due to unfinished test functions, 2008-10-17
python test_merkle.py
python test_permid.py
python test_permid_response1.py
python test_dialback_request.py
python test_extend_hs.py
python test_extend_hs_t350.py
python test_social_overlap.py
python test_gui_server.py
python test_remote_query.py
python test_ut_pex.py
python test_bartercast.py
python test_g2g.py
python test_TimedTaskQueue.py
python test_crawler.py
python test_friendship_crawler.py
python test_multicast.py
python test_url.py
python test_url_metadata.py

./test_sqlitecachedbhandler.sh
./test_secure_overlay.sh
./test_dialback_reply_active.sh
./test_dialback_conn_handler.sh
./test_rquery_reply_active.sh
./test_dlhelp.sh
./test_buddycast_msg.sh
./test_buddycast2_datahandler.sh
# See warning in test_friendship.py
./test_friendship.sh
test_merkle_msg.sh

# Takes a long time, do at end
python test_natcheck.py
