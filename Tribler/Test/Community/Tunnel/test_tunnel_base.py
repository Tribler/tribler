from twisted.internet.defer import inlineCallbacks

from Tribler.Test.Community.AbstractTestCommunity import AbstractTestCommunity
from Tribler.community.hiddentunnel.hidden_community import HiddenTunnelCommunity
from Tribler.community.tunnel.Socks5.server import Socks5Server
from Tribler.community.tunnel.conversion import TunnelConversion
from Tribler.dispersy.requestcache import RequestCache
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class AbstractTestTunnelCommunity(AbstractTestCommunity):

    # We have to initialize Dispersy and the tunnel community on the reactor thread

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self):
        yield super(AbstractTestTunnelCommunity, self).setUp()

        self.tunnel_community = HiddenTunnelCommunity(self.dispersy, self.master_member, self.member)
        self.tunnel_community._request_cache = RequestCache()
        self.tunnel_community.socks_server = Socks5Server(self, 1234)
        self.tunnel_community._initialize_meta_messages()
        self.tunnel_community.add_conversion(TunnelConversion(self.tunnel_community))
