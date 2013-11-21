from Tribler.TrackerChecking.TorrentChecking import TorrentChecking
from Tribler.Core.CacheDB.sqlitecachedb import init as init_db, SQLiteCacheDB
import unittest
import os
from time import sleep

from Tribler.Core.Session import Session
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Test.test_as_server import BASE_DIR, AbstractServer
from Tribler.Core.CacheDB.SqliteCacheDBHandler import TorrentDBHandler, \
    MyPreferenceDBHandler, NetworkBuzzDBHandler
from Tribler.Test.bak_tribler_sdb import FILES_DIR


class TestTorrentChecking(AbstractServer):

    def setUp(self):
        AbstractServer.setUpCleanup(self)

        #config = {}
        #config['state_dir'] = self.getStateDir()
        #config['install_dir'] = '.'
        #init_db(config)
        init_db(self.getStateDir(), config)

        self.tdb = TorrentDBHandler.getInstance()
        self.tdb.torrent_dir = FILES_DIR
        self.tdb.mypref_db = MyPreferenceDBHandler.getInstance()
        self.tdb._nb = NetworkBuzzDBHandler.getInstance()

        self.torrentChecking = TorrentChecking.getInstance()
        sleep(5)

    def test_torrent_checking(self):
        tdef = TorrentDef.load(os.path.join(BASE_DIR, "data", "Pioneer.One.S01E06.720p.x264-VODO.torrent"))
        tdef.set_tracker("http://95.211.198.141:2710/announce")
        tdef.metainfo_valid = True

        self.tdb.addExternalTorrent(tdef)
        self.torrentChecking._test_checkInfohash(tdef.get_infohash(), tdef.get_tracker())
        sleep(30)

        id, num_leechers, num_seeders, last_check = self.tdb.getSwarmInfoByInfohash(tdef.get_infohash())
        assert num_leechers >= 0 or num_seeders >= 0, (num_leechers, num_seeders)

    def tearDown(self):
        self.torrentChecking.shutdown()
        TorrentChecking.delInstance()

        if SQLiteCacheDB.hasInstance():
            SQLiteCacheDB.getInstance().close_all()
            SQLiteCacheDB.delInstance()

        if Session.has_instance():
            Session.del_instance()

        TorrentDBHandler.delInstance()
        MyPreferenceDBHandler.delInstance()
        NetworkBuzzDBHandler.delInstance()

        AbstractServer.tearDownCleanup(self)
