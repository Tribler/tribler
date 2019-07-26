from __future__ import absolute_import

import os
from binascii import hexlify, unhexlify
from threading import RLock

from anydex.core.community import MarketCommunity

from ipv8.attestation.trustchain.community import TrustChainCommunity

from twisted.internet.defer import Deferred, inlineCallbacks

from Tribler.Core.APIImplementation.LaunchManyCore import TriblerLaunchMany
from Tribler.Core.Config.download_config import DownloadConfig
from Tribler.Core.Modules.payout_manager import PayoutManager
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Utilities.bootstrap_util import create_dummy_sql_dumb
from Tribler.Core.Utilities.configparser import CallbackConfigParser
from Tribler.Core.bootstrap import Bootstrap
from Tribler.Core.simpledefs import DLSTATUS_DOWNLOADING, DLSTATUS_METADATA, DLSTATUS_SEEDING, DLSTATUS_STOPPED_ON_ERROR
from Tribler.Test.Core.base_test import MockObject, TriblerCoreTest
from Tribler.Test.test_as_server import TestAsServer
from Tribler.Test.tools import trial_timeout
from Tribler.community.gigachannel.community import GigaChannelCommunity


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
        self.lm.session.config.get_bootstrap_download = lambda: '0' * 20
        self.lm.session.config.get_state_dir = lambda: self.state_dir

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
        tdef.get_infohash = lambda: b'aaaa'
        fake_peer = {'extended_version': 'Tribler', 'id': 'a' * 20, 'dtotal': 10 * 1024 * 1024}
        fake_download = MockObject()
        fake_download.get_def = lambda: tdef
        fake_download.get_def().get_name_as_unicode = lambda: "test.iso"
        fake_download.get_peerlist = lambda: [fake_peer]
        fake_download.hidden = False
        dl_state = MockObject()
        dl_state.get_infohash = lambda: b'aaaa'
        dl_state.get_status = lambda: DLSTATUS_SEEDING
        dl_state.get_download = lambda: fake_download
        fake_config = MockObject()
        fake_config.get_hops = lambda: 0
        fake_config.get_safe_seeding = lambda: True
        fake_download.config = fake_config

        return fake_download, dl_state

    def test_resume_download(self):
        good = []

        def mock_add(tdef, dscfg, setupDelay=None):
            good.append(1)
        self.lm.add = mock_add

        # Try opening real state file
        state = os.path.abspath(os.path.join(self.DATA_DIR, u"config_files",
                                             u"13a25451c761b1482d3e85432f07c4be05ca8a56.conf"))
        self.lm.resume_download(state)
        self.assertTrue(good)

        # Try opening nonexistent file
        good = []
        self.lm.resume_download("nonexistent_file")
        self.assertFalse(good)

        # Try opening corrupt file
        config_file_path = os.path.abspath(os.path.join(self.DATA_DIR, u"config_files",
                                                        u"corrupt_session_config.conf"))
        self.lm.resume_download(config_file_path)
        self.assertFalse(good)

    def test_load_download_config(self):
        """
        Testing whether a DownloadConfig is successfully loaded
        """
        config_file_path = os.path.abspath(os.path.join(self.DATA_DIR, u"config_files", u"config1.conf"))
        config = self.lm.load_download_config(config_file_path)
        self.assertIsInstance(config, DownloadConfig)
        self.assertEqual(int(config.config['general']['version']), 11)

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

        self.lm.downloads = {b'aaaa': fake_error_download}
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
        self.lm.downloads = {b'aaaa': fake_download}
        self.lm.sesscb_states_callback([dl_state])

        self.assertTrue(self.lm.payout_manager.tribler_peers)

    def test_load_checkpoint(self):
        """
        Test whether we are resuming downloads after loading checkpoint
        """

        def mocked_resume_download(filename, setupDelay=3):
            self.assertTrue(filename.endswith('abcd.conf'))
            self.assertEqual(setupDelay, 0)
            mocked_resume_download.called = True

        mocked_resume_download.called = False
        self.lm.session.get_downloads_config_dir = lambda: self.session_base_dir

        with open(os.path.join(self.lm.session.get_downloads_config_dir(), 'abcd.conf'), 'wb') as state_file:
            state_file.write(b"hi")

        self.lm.initComplete = True
        self.lm.resume_download = mocked_resume_download
        self.lm.load_checkpoint()
        self.assertTrue(mocked_resume_download.called)

    def test_resume_empty_download(self):
        """
        Test whether download resumes with faulty pstate file.
        """

        def mocked_add_download():
            mocked_add_download.called = True

        mocked_add_download.called = False
        self.lm.session.get_downloads_pstate_dir = lambda: self.session_base_dir
        self.lm.add = lambda tdef, dscfg: mocked_add_download()

        # Empty pstate file
        pstate_filename = os.path.join(self.lm.session.get_downloads_pstate_dir(), 'abcd.state')
        with open(pstate_filename, 'wb') as state_file:
            state_file.write(b"")

        self.lm.resume_download(pstate_filename)
        self.assertFalse(mocked_add_download.called)


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
        config_sections = ['libtorrent', 'bootstrap', 'trustchain', 'ipv8']

        for section in config_sections:
            self.config.config[section]['enabled'] = True

        self.bootstrap = Bootstrap(self.config.get_state_dir())
        self.tdef = create_dummy_sql_dumb(self.bootstrap.bootstrap_file)
        self.config.set_bootstrap_infohash(hexlify(self.tdef.infohash))

        self.config.set_tunnel_community_socks5_listen_ports(self.get_socks5_ports())
        self.config.set_ipv8_bootstrap_override("127.0.0.1:12345")  # So we do not contact the real trackers

    def downloader_state_callback(self, ds):
        if ds.get_status() == DLSTATUS_SEEDING:
            self.test_deferred.callback(None)
            try:
                os.remove(self.bootstrap.bootstrap_file)
            except OSError:
                pass
            return 0.0
        return 0.5

    @trial_timeout(20)
    def test_bootstrap_seeder(self):
        self.session.lm.start_bootstrap_download()
        self.assertTrue(self.tdef.infohash in self.session.lm.downloads)
        self.assertIsNotNone(self.session.lm.bootstrap.download)
        self.session.lm.bootstrap.download.set_state_callback(self.downloader_state_callback)
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
        config_sections = ['bootstrap', 'libtorrent']

        for section in config_sections:
            self.config.config[section]['enabled'] = True
        self.config.set_bootstrap_infohash("200a4aeb677a04817f1043e8d24591818c7e827c")

    def downloader_state_callback(self, ds):
        if ds.get_status() == DLSTATUS_METADATA or ds.get_status() == DLSTATUS_DOWNLOADING:
            self.test_deferred.callback(None)
            return 0.0
        return 0.5

    @trial_timeout(20)
    def test_bootstrap_downloader(self):
        infohash = self.config.get_bootstrap_infohash()
        self.session.lm.start_bootstrap_download()
        self.assertIsNotNone(self.session.lm.bootstrap)
        self.assertTrue(unhexlify(infohash) in self.session.lm.downloads,
                        "Infohash %s Should be in downloads" % infohash)
        self.session.lm.bootstrap.download.set_state_callback(self.downloader_state_callback)
        return self.test_deferred
