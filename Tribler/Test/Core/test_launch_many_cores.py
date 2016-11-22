import os

from nose.tools import raises
from twisted.internet.defer import Deferred

from Tribler.Core import NoDispersyRLock
from Tribler.Core.APIImplementation.LaunchManyCore import TriblerLaunchMany
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Utilities.configparser import CallbackConfigParser
from Tribler.Core.Utilities.twisted_thread import deferred
from Tribler.Core.exceptions import DuplicateDownloadException
from Tribler.Core.simpledefs import DLSTATUS_STOPPED_ON_ERROR, DLSTATUS_SEEDING
from Tribler.Test.Core.base_test import TriblerCoreTest, MockObject
from Tribler.Test.test_as_server import TestAsServer
from Tribler.community.allchannel.community import AllChannelCommunity
from Tribler.community.bartercast4.community import BarterCommunity
from Tribler.community.multichain.community import MultiChainCommunity
from Tribler.community.search.community import SearchCommunity
from Tribler.community.tunnel.hidden_community import HiddenTunnelCommunity
from Tribler.dispersy.discovery.community import DiscoveryCommunity


class TestLaunchManyCore(TriblerCoreTest):
    """
    This class contains various small unit tests for the LaunchManyCore class.
    """
    DATA_DIR = os.path.join(os.path.abspath(os.path.dirname(os.path.realpath(__file__))), 'data')

    def setUp(self, annotate=True):
        TriblerCoreTest.setUp(self, annotate=annotate)
        self.lm = TriblerLaunchMany()
        self.lm.sesslock = NoDispersyRLock()
        self.lm.session = MockObject()

        # Ignore notifications
        mock_notifier = MockObject()
        mock_notifier.notify = lambda *_: None
        self.lm.session.notifier = mock_notifier

    @raises(ValueError)
    def test_add_tdef_not_finalized(self):
        """
        Testing whether a ValueError is raised when a non-finalized tdef is added as download.
        """
        self.lm.add(TorrentDef(), None)

    @raises(DuplicateDownloadException)
    def test_add_duplicate_download(self):
        """
        Testing whether a DuplicateDownloadException is raised when a download is added twice
        """
        self.lm.downloads = {"abcd": None}
        tdef = TorrentDef()
        tdef.metainfo_valid = True
        tdef.infohash = "abcd"
        self.lm.add(tdef, None)

    def test_load_download_pstate(self):
        """
        Testing whether a pstate is successfully loaded
        """
        config_file_path = os.path.abspath(os.path.join(self.DATA_DIR, u"config_files", u"config1.conf"))
        config = self.lm.load_download_pstate(config_file_path)
        self.assertIsInstance(config, CallbackConfigParser)
        self.assertEqual(config.get('general', 'version'), 11)

    def test_sessconfig_changed_cb(self):
        """
        Testing whether the callback works correctly when changing session config parameters
        """
        self.assertFalse(self.lm.sessconfig_changed_callback('blabla', 'fancyname', '3', '4'))
        self.lm.ltmgr = MockObject()

        def mocked_set_utp(val):
            self.assertEqual(val, '42')
            mocked_set_utp.called = True

        self.lm.ltmgr.set_utp = mocked_set_utp
        mocked_set_utp.called = False
        self.assertTrue(self.lm.sessconfig_changed_callback('libtorrent', 'utp', '42', '3'))
        self.assertTrue(mocked_set_utp.called)
        self.assertTrue(self.lm.sessconfig_changed_callback('libtorrent', 'anon_listen_port', '42', '43'))

    @deferred(timeout=10)
    def test_dlstates_cb_error(self):
        """
        Testing whether a download is stopped on error in the download states callback in LaunchManyCore
        """
        error_stop_deferred = Deferred()

        def mocked_stop():
            error_stop_deferred.callback(None)

        error_tdef = TorrentDef()
        error_tdef.get_infohash = lambda: 'aaaa'
        fake_error_download = MockObject()
        fake_error_download.get_def = lambda: error_tdef
        fake_error_download.get_def().get_name_as_unicode = lambda: "test.iso"
        fake_error_download.stop = mocked_stop
        fake_error_state = MockObject()
        fake_error_state.get_infohash = lambda: 'aaaa'
        fake_error_state.get_error = lambda: "test error"
        fake_error_state.get_status = lambda: DLSTATUS_STOPPED_ON_ERROR
        fake_error_state.get_download = lambda: fake_error_download

        self.lm.downloads = {'aaaa': fake_error_download}
        self.lm.sesscb_states_callback([fake_error_state])

        return error_stop_deferred

    @deferred(timeout=10)
    def test_dlstates_cb_seeding(self):
        """
        Testing whether a download is readded when safe seeding in the download states callback in LaunchManyCore
        """
        readd_deferred = Deferred()

        def mocked_start_download(tdef, dscfg):
            self.assertEqual(tdef, seed_tdef)
            self.assertEqual(dscfg, seed_download)
            readd_deferred.callback(None)

        def mocked_remove_download(download):
            self.assertEqual(download, seed_download)

        self.lm.session.start_download_from_tdef = mocked_start_download
        self.lm.session.remove_download = mocked_remove_download

        seed_tdef = TorrentDef()
        seed_tdef.get_infohash = lambda: 'aaaa'
        seed_download = MockObject()
        seed_download.get_def = lambda: seed_tdef
        seed_download.get_def().get_name_as_unicode = lambda: "test.iso"
        seed_download.get_hops = lambda: 0
        seed_download.get_safe_seeding = lambda: True
        seed_download.copy = lambda: seed_download
        seed_download.set_hops = lambda _: None
        fake_seed_download_state = MockObject()
        fake_seed_download_state.get_infohash = lambda: 'aaaa'
        fake_seed_download_state.get_status = lambda: DLSTATUS_SEEDING
        fake_seed_download_state.get_download = lambda: seed_download

        self.lm.sesscb_states_callback([fake_seed_download_state])

        return readd_deferred


class TestLaunchManyCoreFullSession(TestAsServer):
    """
    This class contains tests that tests methods in LaunchManyCore when a full session is started.
    """

    def setUpPreSession(self):
        TestAsServer.setUpPreSession(self)

        # Enable all communities
        config_sections = ['search_community', 'multichain', 'allchannel_community', 'barter_community',
                           'channel_community', 'preview_channel_community', 'tunnel_community', 'dispersy']

        for section in config_sections:
            self.config.sessconfig.set(section, 'enabled', True)

        self.config.set_megacache(True)
        self.config.set_tunnel_community_socks5_listen_ports(self.get_socks5_ports())
        self.config.set_mainline_dht(True)

    def get_community(self, community_cls):
        for community in self.session.get_dispersy_instance().get_communities():
            if isinstance(community, community_cls):
                return community

    def test_load_communities(self):
        """
        Testing whether all Dispersy communities can be succesfully loaded
        """
        self.assertTrue(self.get_community(DiscoveryCommunity))
        self.assertTrue(self.session.lm.initComplete)
        self.assertTrue(self.get_community(BarterCommunity))
        self.assertTrue(self.get_community(SearchCommunity))
        self.assertTrue(self.get_community(AllChannelCommunity))
        self.assertTrue(self.get_community(HiddenTunnelCommunity))
        self.assertTrue(self.get_community(MultiChainCommunity))
