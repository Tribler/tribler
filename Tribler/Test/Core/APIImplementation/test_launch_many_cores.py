import os

from nose.tools import raises

from Tribler.Core import NoDispersyRLock
from Tribler.Core.APIImplementation.LaunchManyCore import TriblerLaunchMany
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Core.Utilities.configparser import CallbackConfigParser
from Tribler.Core.exceptions import DuplicateDownloadException
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
