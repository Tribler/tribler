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
