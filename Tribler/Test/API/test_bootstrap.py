from __future__ import absolute_import

import logging
import os
import random
from binascii import hexlify
from twisted.internet.defer import Deferred
from twisted.internet.defer import inlineCallbacks

from six.moves import xrange

from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.simpledefs import DLSTATUS_SEEDING, dlstatus_strings
from Tribler.Test.test_as_server import TESTS_DATA_DIR
from Tribler.Test.test_as_server import TestAsServer
from Tribler.Test.tools import trial_timeout


def create_dummy_tdef(file_name, length):
    """
    Create torrent def for dummy file of length MB
    :param file_name: path to save test file
    :param length: Length in MB, e.g. length=15 will generate file of 15 MB
    :return: torrent def with test file
    """
    if not os.path.exists(file_name):
        random.seed(42)
        with open(file_name, 'wb') as fp:
            fp.write(bytearray(random.getrandbits(8) for _ in xrange(length * 1024 * 1024)))
    tdef = TorrentDef()
    tdef.add_content(file_name)
    tdef.set_piece_length(2 ** 16)
    tdef.save()
    return tdef


class MockPayoutManager(object):

    def __init__(self):
        self.peers = {}

    def update_peer(self, mid, balance):
        self.peers[mid] = balance

    def do_payout(self):
        return self.peers


class TestBootSeed(TestAsServer):

    @inlineCallbacks
    def tearDown(self):
        yield super(TestBootSeed, self).tearDown()
        os.remove(self.sourcefn)

    @inlineCallbacks
    def setUp(self):
        yield super(TestBootSeed, self).setUp()
        self._logger = logging.getLogger(self.__class__.__name__)
        self.test_deferred = Deferred()
        self.sourcefn = os.path.join(TESTS_DATA_DIR, 'bootstrap.block')
        self.tdef = create_dummy_tdef(self.sourcefn, 25)
        self._logger.debug("Creating file with infohash %s", hexlify(self.tdef.infohash))
        self.count = 0
        self.payout_manager = MockPayoutManager()

    def setUpPreSession(self):
        super(TestBootSeed, self).setUpPreSession()
        self.config.set_libtorrent_enabled(True)
        self.config.set_libtorrent_max_download_rate(1)

    def start_download(self, dscfg):
        download = self.session.start_download_from_tdef(self.tdef, dscfg)
        download.set_state_callback(self.downloader_state_callback)
        download.add_peer(("127.0.0.1", self.seeder_session.config.get_libtorrent_port()))

    @trial_timeout(20)
    def test_seeding(self):
        """
        Test whether a torrent is correctly seeded
        """

        def start_download(_):
            dscfg = self.dscfg_seed.copy()
            dscfg.set_dest_dir(self.getDestDir())
            self.start_download(dscfg)

        self.setup_seeder(self.tdef, TESTS_DATA_DIR).addCallback(start_download)
        return self.test_deferred

    def downloader_state_callback(self, ds):
        d = ds.get_download()
        self._logger.info("download status: %s %s %s",
                          repr(d.get_def().get_name()),
                          dlstatus_strings[ds.get_status()],
                          ds.get_progress())
        peer_list2 = ds.get_peerlist()
        for p in peer_list2:
            self._logger.info("Peer %s %s %s %s %s",
                              p["ip"], p["id"], p["port"], p["dtotal"], p["utotal"])
            self.payout_manager.update_peer(p["id"], p["dtotal"])

        if ds.get_status() == DLSTATUS_SEEDING:
            peers = self.payout_manager.do_payout()
            self.assertEqual(len(peers), 1, "More than one peer in peer count")
            for p_id, balance in peers.iteritems():
                self._logger.info("Peer %s with balance %s", p_id, balance)
                self.assertGreater(balance, 1, "Balance must be more than 1 MB")
            self.test_deferred.callback(None)
            return 0.0
        return 0.1
