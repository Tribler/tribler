from Tribler.Test.test_as_server import AbstractServer
from Tribler.community.tunnel.conversion import TunnelConversion
from Tribler.community.tunnel.hidden_community import HiddenTunnelCommunity
from Tribler.community.tunnel.routing import Circuit, RelayRoute
from Tribler.community.tunnel.tunnel_community import TunnelExitSocket
from Tribler.dispersy.candidate import Candidate
from Tribler.dispersy.dispersy import Dispersy
from Tribler.dispersy.endpoint import ManualEnpoint
from Tribler.dispersy.member import DummyMember
from Tribler.dispersy.message import DropMessage
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestTunnelCommunity(AbstractServer):

    # We have to initialize Dispersy and the tunnel community on the reactor thread
    @blocking_call_on_reactor_thread
    def setUp(self):
        super(TestTunnelCommunity, self).setUp()

        self.dispersy = Dispersy(ManualEnpoint(0), self.getStateDir())
        self.dispersy._database.open()
        self.master_member = DummyMember(self.dispersy, 1, "a" * 20)
        self.member = self.dispersy.get_new_member(u"curve25519")
        self.tunnel_community = HiddenTunnelCommunity(self.dispersy, self.master_member, self.member)
        self.tunnel_community._initialize_meta_messages()
        self.tunnel_community.add_conversion(TunnelConversion(self.tunnel_community))

    def test_check_destroy(self):
        # Only the first and last node in the circuit may check a destroy message
        for _ in self.tunnel_community.check_destroy([]):
            raise RuntimeError()

        sock_addr = ("127.0.0.1", 1234)

        meta = self.tunnel_community.get_meta_message(u"destroy")
        msg1 = meta.impl(authentication=(self.member,), distribution=(self.tunnel_community.global_time,),
                         candidate=Candidate(sock_addr, False), payload=(42, 43))
        msg2 = meta.impl(authentication=(self.member,), distribution=(self.tunnel_community.global_time,),
                         candidate=Candidate(sock_addr, False), payload=(43, 44))

        self.tunnel_community.exit_sockets[42] = TunnelExitSocket(42, self.tunnel_community,
                                                                  sock_addr = ("128.0.0.1", 1234))

        for i in self.tunnel_community.check_destroy([msg1]):
            self.assertIsInstance(i, DropMessage)

        self.tunnel_community.exit_sockets = {}
        circuit = Circuit(42L, first_hop=("128.0.0.1", 1234))
        self.tunnel_community.circuits[42] = circuit

        for i in self.tunnel_community.check_destroy([msg1, msg2]):
            self.assertIsInstance(i, DropMessage)

        self.tunnel_community.relay_from_to[42] = RelayRoute(42, sock_addr)
        for i in self.tunnel_community.check_destroy([msg1]):
            self.assertIsInstance(i, type(msg1))
