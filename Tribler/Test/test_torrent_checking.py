from time import sleep
from twisted.internet.defer import inlineCallbacks

from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.simpledefs import NTFY_MYPREFERENCES, NTFY_TORRENTS
from Tribler.Test.common import TORRENT_UBUNTU_FILE
from Tribler.Test.test_as_server import TestAsServer
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestTorrentChecking(TestAsServer):
    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self):
        yield super(TestTorrentChecking, self).setUp()

        self.tdb = self.session.open_dbhandler(NTFY_TORRENTS)
        self.tdb.mypref_db = self.session.open_dbhandler(NTFY_MYPREFERENCES)

    def setUpPreSession(self):
        super(TestTorrentChecking, self).setUpPreSession()
        self.config.set_torrent_checking_enabled(True)
        self.config.set_megacache_enabled(True)
        self.config.set_torrent_store_enabled(True)
        self.config.set_libtorrent_enabled(True)

    def test_torrent_checking(self):
        tdef = TorrentDef.load(TORRENT_UBUNTU_FILE)
        tdef.metainfo_valid = True

        self.tdb.addExternalTorrent(tdef)
        self.session.check_torrent_health(tdef.get_infohash())
        sleep(31)

        torrent = self.tdb.getTorrent(tdef.get_infohash())
        self._logger.debug('got torrent %s', torrent)

        num_seeders = torrent['num_seeders']
        num_leechers = torrent['num_leechers']
        assert num_leechers >= 0 or num_seeders >= 0, "No peers found: leechers: %d seeders: %d" %\
                                                      (num_leechers, num_seeders)

    def test_udp_torrent_checking(self):
        tdef = TorrentDef.load(TORRENT_UBUNTU_FILE)
        tdef.set_tracker("udp://localhost")
        tdef.metainfo_valid = True

        self.tdb.addExternalTorrent(tdef)
        self.session.check_torrent_health(tdef.get_infohash())
        sleep(31)

        torrent = self.tdb.getTorrent(tdef.get_infohash())
        self._logger.debug('got torrent %s', torrent)

        num_seeders = torrent['num_seeders']
        num_leechers = torrent['num_leechers']
        assert num_leechers >= 0 or num_seeders >= 0, \
            "No peers found: leechers: %d seeders: %d" % (num_leechers, num_seeders)
