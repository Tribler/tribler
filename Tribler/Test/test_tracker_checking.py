from Tribler.TrackerChecking.TorrentChecking import TorrentChecking
from Tribler.Core.CacheDB.sqlitecachedb import init as init_db, SQLiteCacheDB
import unittest
import os
from time import sleep
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Test.test_as_server import BASE_DIR, AbstractServer

class TestTorrentChecking(AbstractServer):
    def setUp(self):
        self.setUpCleanup()

        config = {}
        config['state_dir'] = self.getStateDir()
        config['install_dir'] = '.'
        init_db(config)

        self.torrentChecking = TorrentChecking()
        sleep(5)

    def test_torrent_checking(self):
        tdef = TorrentDef.load(os.path.join(BASE_DIR, "data", "Pioneer.One.S01E06.720p.x264-VODO.torrent"))
        self.torrentChecking.torrentdb.addExternalTorrent(tdef)
        self.torrentChecking.addToQueue(tdef.get_infohash())
        sleep(30)

        id, num_leechers, num_seeders, last_check = self.torrentChecking.torrentdb.getSwarmInfoByInfohash(tdef.get_infohash())
        assert num_leechers > 0 or num_seeders > 0, (num_leechers, num_seeders)

    def tearDown(self):
        self.torrentChecking.shutdown()
        TorrentChecking.delInstance()

        if SQLiteCacheDB.hasInstance():
            SQLiteCacheDB.getInstance().close_all()
            SQLiteCacheDB.delInstance()

        self.tearDownCleanup()
