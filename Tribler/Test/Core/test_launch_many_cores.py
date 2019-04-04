from __future__ import absolute_import

import os
from binascii import unhexlify
from threading import RLock

from twisted.internet.defer import Deferred, inlineCallbacks

from Tribler.Core.APIImplementation.LaunchManyCore import TriblerLaunchMany
from Tribler.Core.Modules.payout_manager import PayoutManager
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Utilities.bootstrap_util import create_dummy_tdef
from Tribler.Core.Utilities.configparser import CallbackConfigParser
from Tribler.Core.simpledefs import DLSTATUS_DOWNLOADING, DLSTATUS_METADATA, DLSTATUS_SEEDING, DLSTATUS_STOPPED_ON_ERROR
from Tribler.Test.Core.base_test import MockObject, TriblerCoreTest
from Tribler.Test.test_as_server import TestAsServer
from Tribler.Test.tools import trial_timeout
from Tribler.community.gigachannel.community import GigaChannelCommunity
from Tribler.community.market.community import MarketCommunity
from Tribler.pyipv8.ipv8.attestation.trustchain.community import TrustChainCommunity


class TestLaunchManyCore(TriblerCoreTest):
    """
    This class contains various small unit tests for the LaunchManyCore class.
    """
    DATA_DIR = os.path.join(os.path.abspath(os.path.dirname(os.path.realpath(__file__))), 'data')

    def setUp(self):
        TriblerCoreTest.setUp(self)
        self.lm = TriblerLaunchMany()
        self.lm.session_lock = RLock()
        self.lm.session = MockObject()
        self.lm.session.config = MockObject()
        self.lm.session.config.get_max_upload_rate = lambda: 100
        self.lm.session.config.get_max_download_rate = lambda: 100
        self.lm.session.config.get_default_number_hops = lambda: 0

        # Ignore notifications
        mock_notifier = MockObject()
        mock_notifier.notify = lambda *_: None
        self.lm.session.notifier = mock_notifier

    @staticmethod
    def create_fake_download_and_state():
        """
        Create a fake download and state which can be passed to the global download callback.
        """
        tdef = TorrentDef()
        tdef.get_infohash = lambda: 'aaaa'
        fake_peer = {'extended_version': 'Tribler', 'id': 'a' * 20, 'dtotal': 10 * 1024 * 1024}
        fake_download = MockObject()
        fake_download.get_def = lambda: tdef
        fake_download.get_def().get_name_as_unicode = lambda: "test.iso"
        fake_download.get_hops = lambda: 0
        fake_download.get_safe_seeding = lambda: True
        fake_download.get_peerlist = lambda: [fake_peer]
        dl_state = MockObject()
        dl_state.get_infohash = lambda: 'aaaa'
        dl_state.get_status = lambda: DLSTATUS_SEEDING
        dl_state.get_download = lambda: fake_download

        return fake_download, dl_state

    def test_load_download_pstate(self):
        """
        Testing whether a pstate is successfully loaded
        """
        config_file_path = os.path.abspath(os.path.join(self.DATA_DIR, u"config_files", u"config1.conf"))
        config = self.lm.load_download_pstate(config_file_path)
        self.assertIsInstance(config, CallbackConfigParser)
        self.assertEqual(config.get('general', 'version'), 11)

    @trial_timeout(10)
    def test_dlstates_cb_error(self):
        """
        Testing whether a download is stopped on error in the download states callback in LaunchManyCore
        """
        error_stop_deferred = Deferred()

        def mocked_stop():
            error_stop_deferred.callback(None)

        fake_error_download, fake_error_state = TestLaunchManyCore.create_fake_download_and_state()
        fake_error_download.stop = mocked_stop
        fake_error_state.get_status = lambda: DLSTATUS_STOPPED_ON_ERROR
        fake_error_state.get_error = lambda: "test error"

        self.lm.downloads = {'aaaa': fake_error_download}
        self.lm.sesscb_states_callback([fake_error_state])

        return error_stop_deferred

    def test_readd_download_safe_seeding(self):
        """
        Test whether a download is re-added when doing safe seeding
        """
        readd_deferred = Deferred()

        def mocked_update_download_hops(*_):
            readd_deferred.callback(None)

        self.lm.update_download_hops = mocked_update_download_hops

        fake_download, dl_state = TestLaunchManyCore.create_fake_download_and_state()
        self.lm.downloads = {'aaaa': fake_download}
        self.lm.sesscb_states_callback([dl_state])

        return readd_deferred

    def test_update_payout_balance(self):
        """
        Test whether the balance of peers is correctly updated
        """
        fake_download, dl_state = TestLaunchManyCore.create_fake_download_and_state()
        dl_state.get_status = lambda: DLSTATUS_DOWNLOADING

        fake_tc = MockObject()
        fake_tc.add_listener = lambda *_: None
        self.lm.payout_manager = PayoutManager(fake_tc, None)

        self.lm.state_cb_count = 4
        self.lm.downloads = {'aaaa': fake_download}
        self.lm.sesscb_states_callback([dl_state])

        self.assertTrue(self.lm.payout_manager.tribler_peers)

    def test_load_checkpoint(self):
        """
        Test whether we are resuming downloads after loading checkpoint
        """

        def mocked_resume_download(filename, setupDelay=3):
            self.assertTrue(filename.endswith('abcd.state'))
            self.assertEqual(setupDelay, 0)
            mocked_resume_download.called = True

        mocked_resume_download.called = False
        self.lm.session.get_downloads_pstate_dir = lambda: self.session_base_dir

        with open(os.path.join(self.lm.session.get_downloads_pstate_dir(), 'abcd.state'), 'wb') as state_file:
            state_file.write(b"hi")

        self.lm.initComplete = True
        self.lm.resume_download = mocked_resume_download
        self.lm.load_checkpoint()
        self.assertTrue(mocked_resume_download.called)


class TestLaunchManyCoreFullSession(TestAsServer):
    """
    This class contains tests that tests methods in LaunchManyCore when a full session is started.
    """

    def setUpPreSession(self):
        TestAsServer.setUpPreSession(self)

        # Enable all communities
        config_sections = ['trustchain', 'tunnel_community', 'ipv8', 'dht', 'chant', 'market_community']

        for section in config_sections:
            self.config.config[section]['enabled'] = True

        self.config.set_tunnel_community_socks5_listen_ports(self.get_socks5_ports())
        self.config.set_ipv8_bootstrap_override("127.0.0.1:12345")  # So we do not contact the real trackers

    def get_community(self, overlay_cls):
        for overlay in self.session.get_ipv8_instance().overlays:
            if isinstance(overlay, overlay_cls):
                return overlay

    def test_load_communities(self):
        """
        Testing whether all IPv8 communities can be succesfully loaded
        """
        self.assertTrue(self.session.lm.initComplete)
        self.assertTrue(self.get_community(GigaChannelCommunity))
        self.assertTrue(self.get_community(MarketCommunity))
        self.assertTrue(self.get_community(TrustChainCommunity))


class TestLaunchManyCoreSeederBootstrapSession(TestAsServer):

    def setUpPreSession(self):
        TestAsServer.setUpPreSession(self)

        # Enable all communities
        config_sections = ['trustchain', 'ipv8', 'bootstrap', 'libtorrent']

        for section in config_sections:
            self.config.config[section]['enabled'] = True

        self.full_path = os.path.join(self.config.get_state_dir(), 'bootstrap.block')
        self.tdef = create_dummy_tdef(self.full_path, 25)

    def downloader_state_callback(self, ds):
        if ds.get_status() == DLSTATUS_SEEDING:
            os.remove(self.full_path)
            self.test_deferred.callback(None)
            return 0.0
        return 0.5

    @trial_timeout(20)
    def test_bootstrap_seeder(self):
        self.assertTrue(self.tdef.infohash in self.session.lm.downloads)
        self.assertIsNotNone(self.session.lm.bootstrap_session)
        self.session.lm.bootstrap_session.set_state_callback(self.downloader_state_callback)
        return self.test_deferred

    @inlineCallbacks
    def setUp(self):
        yield super(TestLaunchManyCoreSeederBootstrapSession, self).setUp()
        self.test_deferred = Deferred()


class TestLaunchManyCoreBootstrapSession(TestAsServer):

    @inlineCallbacks
    def setUp(self):
        yield super(TestLaunchManyCoreBootstrapSession, self).setUp()
        self.test_deferred = Deferred()

    def setUpPreSession(self):
        TestAsServer.setUpPreSession(self)

        # Enable all communities
        config_sections = ['trustchain', 'ipv8', 'bootstrap', 'libtorrent']

        for section in config_sections:
            self.config.config[section]['enabled'] = True

    def downloader_state_callback(self, ds):
        if ds.get_status() == DLSTATUS_METADATA:
            self.test_deferred.callback(None)
            return 0.0
        return 0.5

    @trial_timeout(20)
    def test_bootstrap_downloader(self):
        infohash = self.config.get_bootstrap_infohash()
        self.assertIsNotNone(self.session.lm.bootstrap_session)
        self.assertTrue(unhexlify(infohash) in self.session.lm.downloads,
                        "Infohash %s Should be in downloads" % infohash)
        self.session.lm.bootstrap_session.set_state_callback(self.downloader_state_callback)
        return self.test_deferred
