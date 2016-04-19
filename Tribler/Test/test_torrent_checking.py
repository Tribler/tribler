from time import sleep

from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.simpledefs import NTFY_MYPREFERENCES, NTFY_TORRENTS
from Tribler.Test.test_as_server import TestAsServer
from Tribler.Test.test_libtorrent_download import TORRENT_FILE


class TestTorrentChecking(TestAsServer):
    def setUp(self):
        super(TestTorrentChecking, self).setUp()

        self.tdb = self.session.open_dbhandler(NTFY_TORRENTS)
        self.tdb.mypref_db = self.session.open_dbhandler(NTFY_MYPREFERENCES)

    def setUpPreSession(self):
        super(TestTorrentChecking, self).setUpPreSession()
        self.config.set_torrent_checking(True)
        self.config.set_megacache(True)
        self.config.set_torrent_store(True)
        self.config.set_libtorrent(True)

    def test_torrent_checking(self):
        tdef = TorrentDef.load(TORRENT_FILE)
        # TODO(emilon): This tracker is no more, we need to set up a new one
        # tdef.set_tracker("http://95.211.198.141:2710/announce")
        tdef.metainfo_valid = True

        self.tdb.addExternalTorrent(tdef)
        self.session.check_torrent_health(tdef.get_infohash())
        sleep(31)

        torrent = self.tdb.getTorrent(tdef.get_infohash())
        self._logger.debug('got torrent %s', torrent)

        num_seeders = torrent['num_seeders']
        num_leechers = torrent['num_leechers']
        assert num_leechers >= 0 or num_seeders >= 0, "No peers found: leechers: %d seeders: %d" % (
        num_leechers, num_seeders)

    def test_udp_torrent_checking(self):
        tdef = TorrentDef.load(TORRENT_FILE)
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
