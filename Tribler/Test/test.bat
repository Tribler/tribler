
set PYTHONPATH=..\..

REM python test_bsddb2sqlite.py # Arno, 2008-11-26: Alea jacta est.
REM python test_buddycast.py # currently not working due to missing DataHandler functions, 2008-10-17
REM python test_friend.py # Arno, 2008-10-17: need to convert to new DB structure
REM python test_torrentcollecting.py # currently not working due to missing functions, 2009-12-04
python test_TimedTaskQueue.py
python test_buddycast2_datahandler.py
python test_cachingstream.py
python test_closedswarm.py
python test_connect_overlay.py singtest_connect_overlay
python test_crawler.py
python test_dialback_request.py
python test_extend_hs.py
python test_friendship_crawler.py
python test_g2g.py
python test_gui_server.py
python test_merkle.py
python test_multicast.py
python test_osutils.py
python test_permid.py
python test_permid_response1.py
python test_remote_query.py
python test_seeding_stats.py
python test_social_overlap.py
python test_sqlitecachedb.py
python test_status.py
python test_superpeers.py 
python test_url.py
python test_url_metadata.py
python test_ut_pex.py
python test_video_server.py
python test_threadpool.py
python test_miscutils.py

CALL test_buddycast_msg.bat 
CALL test_dialback_conn_handler.bat
CALL test_dialback_reply_active.bat
REM # CALL test_dlhelp.bat       Arno, Disabled replaced with ProxyService
REM # See warning in test_friendship.py
CALL test_friendship.bat        
CALL test_merkle_msg.bat
CALL test_overlay_bridge.bat
CALL test_rquery_reply_active.bat
CALL test_secure_overlay.bat
CALL test_sqlitecachedbhandler.bat
CALL test_vod.bat
CALL test_na_extend_hs.bat
CALL test_channelcast.bat
CALL test_subtitles.bat
REM # CALL test_proxyservice.bat # Arno, not finished
CALL test_proxyservice_as_coord.bat

REM Takes a long time, do at end
python test_natcheck.py

REM ##### ARNO
REM # wait till arno's fixes are merged
REM # python test_buddycast5.py

REM #### NITIN
REM # broken...
REM # python test_searchgridmanager.py

REM ########### Not unittests
REM #
REM # 2010-02-03 Boudewijn: The stresstest works, but does not contain any
REM # actual unittests... it just takes a long time to run
REM # python test_buddycast4_stresstest.py
REM #
REM # 2010-02-03 Boudewijn: Doesn't look like this was ever a unittest
REM # python test_tracker_checking.py

REM ########### Obsolete
REM #
REM # 2010-02-03 Boudewijn: OLD, not using anymore
REM # python test_buddycast4.py 

