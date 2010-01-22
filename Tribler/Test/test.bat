
set PYTHONPATH=..\..

python test_sqlitecachedb.py
REM python test_friend.py # Arno, 2008-10-17: need to convert to new DB structure
python test_superpeers.py 
REM python test_buddycast.py # currently not working due to missing DataHandler functions, 2008-10-17
REM python test_torrentcollecting.py # currently not working due to missing functions, 2009-12-04
REM python test_sim.py # currently not working due to unfinished test functions, 2008-10-17
python test_merkle.py
python test_permid.py
python test_permid_response1.py
python test_dialback_request.py
python test_extend_hs.py
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
python test_status.py
python test_closedswarm.py
python test_cachingstream.py

CALL test_sqlitecachedbhandler.bat
CALL test_secure_overlay.bat
CALL test_dialback_reply_active.bat
CALL test_dialback_conn_handler.bat
CALL test_rquery_reply_active.bat
CALL test_dlhelp.bat
CALL test_buddycast_msg.bat 
CALL test_buddycast2_datahandler.bat
REM # See warning in test_friendship.py
CALL test_friendship.bat
CALL test_merkle_msg.bat
CALL test_vod.bat

REM Takes a long time, do at end
python test_natcheck.py
