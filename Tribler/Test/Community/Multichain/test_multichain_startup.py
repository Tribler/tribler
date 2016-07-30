"""
This file test whether Tribler is able to start when multichain is enabled
Based on test_bartercast4_community.py
"""
from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Utilities.twisted_thread import deferred
from Tribler.Test.test_as_server import TestAsServer
from Tribler.community.multichain.community import MultiChainCommunity, MultiChainCommunityCrawler
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestMultichainStartup(TestAsServer):
    """Start a Tribler session and initialize the multichain community to ensure it does not crash."""

    @deferred(timeout=10)
    @inlineCallbacks
    def test_multichain_startup_no_crawler(self):
        yield self.load_communities(self.session, self.dispersy, False)
        communities = [type(community) for community in self.dispersy._communities.values()]
        assert MultiChainCommunity in communities

    @deferred(timeout=10)
    @inlineCallbacks
    def test_multichain_startup_crawler(self):
        yield self.load_communities(self.session, self.dispersy, True)
        communities = [type(community) for community in self.dispersy._communities.values()]
        assert MultiChainCommunityCrawler in communities

    def setUpPreSession(self):
        super(TestMultichainStartup, self).setUpPreSession()
        self.config.set_enable_multichain(False)
        self.config.set_dispersy(True)
        self.config.set_megacache(True)
        self.config.set_enable_channel_search(True)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def load_communities(self, session, dispersy, crawler=False):
        keypair = dispersy.crypto.generate_key(u"curve25519")
        dispersy_member = yield dispersy.get_member(private_key=dispersy.crypto.key_to_bin(keypair))
        if crawler:
            yield dispersy.define_auto_load(MultiChainCommunityCrawler, dispersy_member, load=True)
        else:
            yield dispersy.define_auto_load(MultiChainCommunity, dispersy_member, load=True)

    def setUp(self):
        super(TestMultichainStartup, self).setUp()
        self.dispersy = self.session.get_dispersy_instance()

    def tearDown(self):
        super(TestMultichainStartup, self).tearDown()
