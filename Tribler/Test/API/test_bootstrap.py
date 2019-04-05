from __future__ import absolute_import

import logging
import os
from binascii import hexlify

from twisted.internet.defer import Deferred
from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Utilities.bootstrap_util import create_dummy_tdef
from Tribler.Core.simpledefs import DLSTATUS_SEEDING, dlstatus_strings
from Tribler.Test.test_as_server import TESTS_DATA_DIR
from Tribler.Test.test_as_server import TestAsServer
from Tribler.Test.tools import trial_timeout


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
        os.remove(self.sourcefn)
        yield super(TestBootSeed, self).tearDown()

    @inlineCallbacks
    def setUp(self):
        yield super(TestBootSeed, self).setUp()
        self._logger = logging.getLogger(self.__class__.__name__)
        self.test_deferred = Deferred()
        self.sourcefn = os.path.join(TESTS_DATA_DIR, 'bootstrap.block')
        self.tdef = create_dummy_tdef(self.sourcefn, 25)
        self._logger.debug("Creating file with infohash %s", hexlify(self.tdef.infohash))
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
    def test_bootstrap(self):
        """
        Test whether a dummy bootstrap file is correctly downloaded and after download a direct payout is made
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
            for p_id, balance in peers.items():
                self._logger.info("Peer %s with balance %s", p_id, balance)
                self.assertGreater(balance, 1, "Balance must be more than 1 MB")
            self.test_deferred.callback(None)
            return 0.0
        return 0.1
