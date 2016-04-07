from Tribler.Test.test_as_server import AbstractServer
from Tribler.community.tunnel.Socks5.server import Socks5Server
from Tribler.community.tunnel.conversion import TunnelConversion
from Tribler.community.tunnel.hidden_community import HiddenTunnelCommunity
from Tribler.dispersy.dispersy import Dispersy
from Tribler.dispersy.endpoint import ManualEnpoint
from Tribler.dispersy.member import DummyMember
from Tribler.dispersy.requestcache import RequestCache
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class AbstractTestTunnelCommunity(AbstractServer):

    # We have to initialize Dispersy and the tunnel community on the reactor thread
    @blocking_call_on_reactor_thread
    def setUp(self):
        super(AbstractTestTunnelCommunity, self).setUp()

        self.dispersy = Dispersy(ManualEnpoint(0), self.getStateDir())
        self.dispersy._database.open()
        self.master_member = DummyMember(self.dispersy, 1, "a" * 20)
        self.member = self.dispersy.get_new_member(u"curve25519")
        self.tunnel_community = HiddenTunnelCommunity(self.dispersy, self.master_member, self.member)
        self.tunnel_community._request_cache = RequestCache()
        self.tunnel_community.socks_server = Socks5Server(self, 1234)
        self.tunnel_community._initialize_meta_messages()
        self.tunnel_community.add_conversion(TunnelConversion(self.tunnel_community))
