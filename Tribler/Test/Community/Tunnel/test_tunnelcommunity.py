import time

from Tribler.Core.Utilities.twisted_thread import deferred
from Tribler.Test.Community.Tunnel.test_tunnel_base import AbstractTestTunnelCommunity
from Tribler.community.tunnel.routing import Circuit, RelayRoute
from Tribler.community.tunnel.tunnel_community import TunnelExitSocket, CircuitRequestCache, PingRequestCache
from Tribler.dispersy.candidate import Candidate
from Tribler.dispersy.message import DropMessage
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TestTunnelCommunity(AbstractTestTunnelCommunity):

    @blocking_call_on_reactor_thread
    def test_circuit_request_cache(self):
        circuit = Circuit(42L)
        circuit_request_cache = CircuitRequestCache(self.tunnel_community, circuit)
        self.tunnel_community.circuits[42] = circuit
        circuit_request_cache.on_timeout()
        self.assertIn(42, self.tunnel_community.circuits)

        circuit._broken = True
        circuit_request_cache.on_timeout()
        self.assertNotIn(42, self.tunnel_community.circuits)

    @blocking_call_on_reactor_thread
    def test_ping_request_cache(self):
        circuit = Circuit(42L)
        ping_request_cache = PingRequestCache(self.tunnel_community, circuit)
        self.assertGreater(ping_request_cache.timeout_delay, 0)
        self.tunnel_community.circuits[42] = circuit

        circuit.last_incoming = time.time() + 1000
        ping_request_cache.on_timeout()
        self.assertIn(42, self.tunnel_community.circuits)

        circuit.last_incoming = time.time() - ping_request_cache.timeout_delay - 200
        ping_request_cache.on_timeout()
        self.assertNotIn(42, self.tunnel_community.circuits)

    @blocking_call_on_reactor_thread
    def test_check_pong(self):
        circuit = Circuit(42L)
        ping_request_cache = PingRequestCache(self.tunnel_community, circuit)
        ping_num = self.tunnel_community.request_cache.add(ping_request_cache).number
        meta = self.tunnel_community.get_meta_message(u"ping")
        msg1 = meta.impl(distribution=(self.tunnel_community.global_time,),
                         candidate=Candidate(("127.0.0.1", 1234), False), payload=(42, ping_num - 1))
        msg2 = meta.impl(distribution=(self.tunnel_community.global_time,),
                         candidate=Candidate(("127.0.0.1", 1234), False), payload=(42, ping_num))

        # Invalid ping identifier
        for i in self.tunnel_community.check_pong([msg1]):
            self.assertIsInstance(i, DropMessage)

        for i in self.tunnel_community.check_pong([msg2]):
            self.assertIsInstance(i, type(msg2))

        self.tunnel_community.request_cache.pop(u"ping", ping_num)

    def test_check_destroy(self):
        # Only the first and last node in the circuit may check a destroy message
        with self.assertRaises(StopIteration):
            next(self.tunnel_community.check_destroy([]))
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

    @deferred(timeout=5)
    def test_send_to_destination_ip(self):
        """
        This test checks if the ip address can be resolved when a destination object
        is set and is_valid_address returns true.
        Will result in an exception as self.transport is not initialized.
        Which is catched by the try except in on_ip_address.
        """
        circuit_id = 1337
        sock_addr = "127.0.0.1"
        exit_tunnel = TunnelExitSocket(circuit_id, self.tunnel_community, sock_addr, False)
        self.tunnel_community.exit_sockets[circuit_id] = exit_tunnel
        exit_tunnel.ips[("127.0.0.1", 8080)] = -1
        data = "ffffffff".decode("HEX") + "1" * 25
        exit_tunnel.sendto(data, ("127.0.0.1", 8080))
        return exit_tunnel.close()


    @deferred(timeout=5)
    def test_send_to_ip_deferred(self):
        """
        This test checks if the ip address can be resolved when a destination object
        is set and is_valid_address returns false.
        Which will be cancelled by the close() function being called immediately.
        """
        circuit_id = 1337
        sock_addr = "127.0.0.1"
        exit_tunnel = TunnelExitSocket(circuit_id, self.tunnel_community, sock_addr, False)
        self.tunnel_community.exit_sockets[circuit_id] = exit_tunnel
        exit_tunnel.ips[("localhost", -1)] = -1
        data = "ffffffff".decode("HEX") + "1" * 25
        exit_tunnel.sendto(data, ("localhost", -1))
        return exit_tunnel.close()
