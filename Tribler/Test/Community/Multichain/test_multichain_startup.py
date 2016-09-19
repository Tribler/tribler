"""
This file test whether Tribler is able to start when multichain is enabled
Based on test_bartercast4_community.py
"""
from Tribler.Test.test_as_server import TestAsServer
from Tribler.community.multichain.community import MultiChainCommunity, MultiChainCommunityCrawler
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestMultichainStartup(TestAsServer):
    """Start a Tribler session and initialize the multichain community to ensure it does not crash."""

    def test_multichain_startup_no_crawler(self):
        self.load_communities(self.session, self.dispersy, False)
        communities = [type(community) for community in self.dispersy._communities.values()]
        assert MultiChainCommunity in communities

    def test_multichain_startup_crawler(self):
        self.load_communities(self.session, self.dispersy, True)
        communities = [type(community) for community in self.dispersy._communities.values()]
        assert MultiChainCommunityCrawler in communities

    def setUpPreSession(self):
        super(TestMultichainStartup, self).setUpPreSession()
        self.config.set_enable_multichain(False)
        self.config.set_dispersy(True)
        self.config.set_megacache(True)
        self.config.set_enable_channel_search(True)

    @blocking_call_on_reactor_thread
    def load_communities(self, session, dispersy, crawler=False):
        keypair = dispersy.crypto.generate_key(u"curve25519")
        dispersy_member = dispersy.get_member(private_key=dispersy.crypto.key_to_bin(keypair))
        kwargs = {'tribler_session': session}
        if crawler:
            dispersy.define_auto_load(MultiChainCommunityCrawler, dispersy_member, load=True, kargs=kwargs)
        else:
            dispersy.define_auto_load(MultiChainCommunity, dispersy_member, load=True, kargs=kwargs)

    def setUp(self):
        super(TestMultichainStartup, self).setUp()
        self.dispersy = self.session.get_dispersy_instance()

    def tearDown(self):
        super(TestMultichainStartup, self).tearDown()
