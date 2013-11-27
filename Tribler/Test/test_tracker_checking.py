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
from Tribler.Core.Session import Session
from Tribler.Core.CacheDB.sqlitecachedb import init as init_db, SQLiteCacheDB
from Tribler.Core.CacheDB.SqliteCacheDBHandler import TorrentDBHandler,\
    MyPreferenceDBHandler, NetworkBuzzDBHandler

from Tribler.Test.test_as_server import BASE_DIR, TestAsServer
from Tribler.Test.bak_tribler_sdb import FILES_DIR


class TestTorrentChecking(TestAsServer):

    def setUp(self):
        TestAsServer.setUp(self)

        #init_db(self.getStateDir(), '.')

        self.tdb = TorrentDBHandler.getInstance()
        self.tdb.mypref_db = MyPreferenceDBHandler.getInstance()
        self.tdb._nb = NetworkBuzzDBHandler.getInstance()

    def setUpPreSession(self):
        TestAsServer.setUpPreSession(self)
        self.config.set_torrent_checking(True)
        self.config.set_megacache(True)

    # ------------------------------------------------------------
    # Unit Test for TorrentChecking thread.
    # ------------------------------------------------------------
    def test_torrent_checking(self):
        self.torrentChecking = TorrentChecking.getInstance()
        sleep(5)

        tdef = TorrentDef.load(os.path.join(BASE_DIR, "data", "Pioneer.One.S01E06.720p.x264-VODO.torrent"))
        tdef.set_tracker("http://95.211.198.141:2710/announce")
        tdef.metainfo_valid = True

        self.tdb.addExternalTorrent(tdef)
        self.torrentChecking.addInfohashRequest(tdef.get_infohash())
        sleep(30)

        id, num_leechers, num_seeders, last_check = self.tdb.getSwarmInfoByInfohash(tdef.get_infohash())
        assert num_leechers >= 0 or num_seeders >= 0, (num_leechers, num_seeders)