from Tribler.Test.test_as_server import TestAsServer
from Tribler.community.allchannel.community import AllChannelCommunity
from Tribler.community.bartercast4.community import BarterCommunity
from Tribler.community.multichain.community import MultiChainCommunity
from Tribler.community.search.community import SearchCommunity
from Tribler.community.tunnel.hidden_community import HiddenTunnelCommunity
from Tribler.dispersy.discovery.community import DiscoveryCommunity


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
