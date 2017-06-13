"""
This file test whether Tribler is able to start when TriblerChain is enabled.
"""
from twisted.internet.defer import inlineCallbacks

from Tribler.Test.test_as_server import TestAsServer
from Tribler.community.triblerchain.community import TriblerChainCommunity, TriblerChainCommunityCrawler
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestTrustchainStartup(TestAsServer):
    """
    Start a Tribler session and initialize the TriblerChain community to ensure it does not crash.
    """

    def test_trustchain_startup_no_crawler(self):
        self.load_communities(self.session, self.dispersy, False)
        communities = [type(community) for community in self.dispersy._communities.values()]
        assert TriblerChainCommunity in communities

    def test_trustchain_startup_crawler(self):
        self.load_communities(self.session, self.dispersy, True)
        communities = [type(community) for community in self.dispersy._communities.values()]
        assert TriblerChainCommunityCrawler in communities

    def setUpPreSession(self):
        super(TestTrustchainStartup, self).setUpPreSession()
        self.config.set_trustchain_enabled(False)
        self.config.set_dispersy_enabled(True)
        self.config.set_megacache_enabled(True)
        self.config.set_channel_search_enabled(True)

    @blocking_call_on_reactor_thread
    def load_communities(self, session, dispersy, crawler=False):
        keypair = dispersy.crypto.generate_key(u"curve25519")
        dispersy_member = dispersy.get_member(private_key=dispersy.crypto.key_to_bin(keypair))
        kwargs = {'tribler_session': session}
        if crawler:
            dispersy.define_auto_load(TriblerChainCommunityCrawler, dispersy_member, load=True, kargs=kwargs)
        else:
            dispersy.define_auto_load(TriblerChainCommunity, dispersy_member, load=True, kargs=kwargs)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, autoload_discovery=True):
        yield super(TestTrustchainStartup, self).setUp(autoload_discovery=autoload_discovery)
        self.dispersy = self.session.get_dispersy_instance()
