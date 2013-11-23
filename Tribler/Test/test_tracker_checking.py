import os
import sys
import unittest
from time import sleep
import binascii
from threading import Event
import select

from Tribler.TrackerChecking.TorrentChecking import TorrentChecking
from Tribler.TrackerChecking.TrackerInfoCache import TrackerInfoCache
from Tribler.TrackerChecking.TrackerSession import TrackerSession

from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.CacheDB.sqlitecachedb import init as init_db, SQLiteCacheDB
from Tribler.Core.CacheDB.SqliteCacheDBHandler import TorrentDBHandler,\
    MyPreferenceDBHandler, NetworkBuzzDBHandler

from Tribler.Test.test_as_server import BASE_DIR, AbstractServer
from Tribler.Test.bak_tribler_sdb import FILES_DIR


class TestTorrentChecking(AbstractServer):

    def setUp(self):
        self.setUpCleanup()

        init_db(self.getStateDir(), '.')

        self.tdb = TorrentDBHandler.getInstance()
        self.tdb.torrent_dir = FILES_DIR
        self.tdb.mypref_db = MyPreferenceDBHandler.getInstance()
        self.tdb._nb = NetworkBuzzDBHandler.getInstance()

    # ------------------------------------------------------------
    # Unit Test for TrackerInfoCache.
    # ------------------------------------------------------------
    def test_tracker_info_cache(self):
        print >> sys.stderr, 'Testing TrackerInfoCache ...'

        tracker_info_cache = TrackerInfoCache()
        tracker_info_cache.loadCacheFromDb()
        cache_initialize_timeout = 5
        cache_initialized = tracker_info_cache.isCacheInitialized(cache_initialize_timeout)
        assert cache_initialized, 'Failed to initialize within %d seconds' % cache_initialize_timeout

        tracker = 'udp://tracker.publicbt.com:80/announce'
        # > subtest 1: update a valid tracker.
        tracker_info_cache.updateTrackerInfo(tracker, success=True)
        do_check_tracker = tracker_info_cache.toCheckTracker(tracker)
        assert do_check_tracker == True, 'Failed to update good tracker'

        # > subtest 2: update several failures.
        for i in xrange(10):
            tracker_info_cache.updateTrackerInfo(tracker, success=False)
        do_check_tracker = tracker_info_cache.toCheckTracker(tracker)
        assert do_check_tracker == False, 'Failed to update bad tracker'

        # > subtest 3: update a valid check.
        tracker_info_cache.updateTrackerInfo(tracker, success=True)
        do_check_tracker = tracker_info_cache.toCheckTracker(tracker)
        assert do_check_tracker == True, 'Failed to update good tracker again'

        del tracker_info_cache

    # ------------------------------------------------------------
    # Unit Test for TrackerSession.
    # TODO: The hard coded timeout may be changed later.
    # ------------------------------------------------------------
    def test_tracker_session(self):
        global tracker_session_result

        # the callback function for TrackerSession
        def getResult(infohash, seeders, leechers):
            global tracker_session_result
            tracker_session_result = (infohash, seeders, leechers)

        # because everything is non-blocking here, it's a bit ugly.
        # UDP tracker
        tracker = 'udp://tracker.publicbt.com:80/announce'
        infohash = binascii.a2b_hex('c798357393a0bcb0a64f564072fd224f942125b7')
        success = False
        tracker_session_result = None
        print >> sys.stderr, 'Testing UDP TrackerSession ...'
        try:
            tracker_session = TrackerSession.createSession(tracker, getResult)
            tracker_session.addInfohash(infohash)
            tracker_session.establishConnection()

            # finsh connection
            sockList = [tracker_session.getSocket()]
            rl, wl, el = select.select(sockList, [], [], 10)
            if not rl or tracker_session.hasFailed():
                assert False, 'TrackerSession too slow or failed.'
            tracker_session.handleRequest()
            if tracker_session.hasFailed():
                assert False, 'TrackerSession failed.'

            # handle results
            rl, wl, el = select.select(sockList, [], [], 10)
            if not rl or tracker_session.hasFailed():
                assert False, 'TrackerSession too slow or failed.'
            tracker_session.handleRequest()
            if tracker_session.hasFailed():
                assert False, 'TrackerSession failed.'

            # check results
            if tracker_session_result:
                if infohash == tracker_session_result[0] and\
                        tracker_session_result[1] >= 0 and tracker_session_result[2] >= 0:
                    success = True
                else:
                    print >> sys.stderr, 'Invalid result s/l=(%d/%d) on tracker.' %\
                        (tracker_session_result[1], tracker_session_result[2])
                    success = False
            else:
                success = False
        except Exception as e:
            print >> sys.stderr, 'UDP TrackerSession error:', e
            success = False
        tracker_session.cleanup()
        del tracker_session
        assert success, 'UDP TrackerSession failed.'

        # HTTP tracker
        tracker = 'http://www.mvgroup.org:2710/announce'
        infohash = binascii.a2b_hex('06b9ca5d2616b608ba5dedc63b7435a98c9c8e3e')
        success = False
        tracker_session_result = None
        print >> sys.stderr, 'Testing HTTP TrackerSession ...'
        try:
            tracker_session = TrackerSession.createSession(tracker, getResult)
            tracker_session.addInfohash(infohash)
            tracker_session.establishConnection()

            # finsh connection
            sockList = [tracker_session.getSocket()]
            rl, wl, el = select.select([], sockList, [], 10)
            if not wl or tracker_session.hasFailed():
                assert False, 'TrackerSession too slow or failed.'
            tracker_session.handleRequest()
            if tracker_session.hasFailed():
                assert False, 'TrackerSession failed.'

            # handle results
            rl, wl, el = select.select(sockList, [], [], 10)
            if not rl or tracker_session.hasFailed():
                assert False, 'TrackerSession too slow or failed.'
            tracker_session.handleRequest()
            if tracker_session.hasFailed():
                assert False, 'TrackerSession failed.'

            # check results
            if tracker_session_result:
                if infohash == tracker_session_result[0] and\
                        tracker_session_result[1] >= 0 and tracker_session_result[2] >= 0:
                    success = True
                else:
                    print >> sys.stderr, 'Invalid result s/l=(%d/%d) on tracker.' %\
                        (tracker_session_result[1], tracker_session_result[2])
                    success = False
            else:
                success = False
        except Exception as e:
            print >> sys.stderr, 'HTTP TrackerSession error:', e
            success = False
        tracker_session.cleanup()
        del tracker_session
        assert success, 'HTTP TrackerSession failed.'

    # ------------------------------------------------------------
    # Unit Test for TorrentChecking thread.
    # ------------------------------------------------------------
    def test_torrent_checking(self):
        self.torrentChecking = TorrentChecking()
        sleep(5)

        tdef = TorrentDef.load(os.path.join(BASE_DIR, "data", "Pioneer.One.S01E06.720p.x264-VODO.torrent"))
        tdef.set_tracker("http://95.211.198.141:2710/announce")
        tdef.metainfo_valid = True

        self.tdb.addExternalTorrent(tdef)
        self.torrentChecking.addToQueue(tdef.get_infohash())
        sleep(30)

        id, num_leechers, num_seeders, last_check = self.tdb.getSwarmInfoByInfohash(tdef.get_infohash())
        assert num_leechers >= 0 or num_seeders >= 0, (num_leechers, num_seeders)

        self.torrentChecking.shutdown()
        TorrentChecking.delInstance()

    def tearDown(self):

        if SQLiteCacheDB.hasInstance():
            SQLiteCacheDB.getInstance().close_all()
            SQLiteCacheDB.delInstance()

        TorrentDBHandler.delInstance()
        MyPreferenceDBHandler.delInstance()
        NetworkBuzzDBHandler.delInstance()

        self.tearDownCleanup()
