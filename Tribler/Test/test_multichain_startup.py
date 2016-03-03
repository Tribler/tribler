"""
This file test whether Tribler is able to start when multichain is enabled
Based on test_bartercast4_community.py
"""
from Tribler.Test.test_as_server import TestAsServer
from Tribler.community.multichain.community import MultiChainCommunity, MultiChainCommunityCrawler
from Tribler.community.tunnel.tunnel_community import TunnelSettings

from Tribler.dispersy.util import blocking_call_on_reactor_thread

from time import sleep


class TestMultichainStartup(TestAsServer):

    """Start a Tribler session and ensure it does not crash."""

    def __init__(self, *argv, **kwargs):
        super(TestMultichainStartup, self).__init__(*argv, **kwargs)

    def test_multichain_startup(self):
        sleep(5)

    def setUpPreSession(self):
        super(TestMultichainStartup, self).setUpPreSession()
        self.config.set_dispersy(True)
        self.config.set_megacache(True)
        self.config.set_enable_channel_search(True)

    @blocking_call_on_reactor_thread
    def load_communities(self, session, dispersy, crawler=False):
        keypair = dispersy.crypto.generate_key(u"curve25519")
        dispersy_member = dispersy.get_member(private_key=dispersy.crypto.key_to_bin(keypair))
        settings = TunnelSettings(tribler_session=session)
        settings.become_exitnode = False
        if crawler:
            dispersy.define_auto_load(MultiChainCommunityCrawler, dispersy_member, (session, settings), load=True)
        else:
            dispersy.define_auto_load(MultiChainCommunity, dispersy_member, (session, settings), load=True)

    def setUp(self):
        super(TestMultichainStartup, self).setUp()
        self.dispersy = self.session.get_dispersy_instance()
        self.load_communities(self.session, self.dispersy, True)

    def tearDown(self):
        super(TestMultichainStartup, self).tearDown()
