import logging

from twisted.python import log
from twisted.internet import defer

from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB
from Tribler.Core.Session import Session
from Tribler.Core.SessionConfig import SessionStartupConfig
from Tribler.Core.Utilities.misc_utils import printDBStats, compute_ratio
from Tribler.Core.Utilities.twisted_thread import deferred
from Tribler.Test.test_as_server import AbstractServer


class TriblerCoreUtilitiesTestMiscUtilities(AbstractServer):

    @deferred()
    def test_print_DB_stats(self):
        self.config = SessionStartupConfig()
        self.config.set_state_dir(self.getStateDir())
        self.config.set_torrent_checking(False)
        self.config.set_multicast_local_peer_discovery(False)
        self.config.set_megacache(False)
        self.config.set_dispersy(False)
        self.config.set_mainline_dht(False)
        self.config.set_torrent_collecting(False)
        self.config.set_libtorrent(False)
        self.config.set_dht_torrent_collecting(False)
        self.config.set_videoplayer(False)
        self.session = Session(self.config, ignore_singleton=True)
        self.session.sqlite_db = SQLiteCacheDB(self.session)
        self.db_path = u":memory:"
        self.session.sqlite_db.initialize(self.db_path)

        self._logger = logging.getLogger(self.__class__.__name__)

        d = defer.maybeDeferred(printDBStats, self._logger, self.session)
        d.addErrback(log.err)

        return d


    def test_compute_ratio(self):
        assert(compute_ratio(1337, 0) == "1337 / 0 ~0.0%")
        assert(compute_ratio(1337, 42) == "1337 / 42 ~3183.3%")

