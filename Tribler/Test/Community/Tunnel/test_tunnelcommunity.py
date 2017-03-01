import time
from twisted.internet.defer import inlineCallbacks, returnValue

from Tribler.Test.Community.Tunnel.test_tunnel_base import AbstractTestTunnelCommunity
from Tribler.Test.twisted_thread import deferred
from Tribler.community.tunnel.conversion import TunnelConversion
from Tribler.community.tunnel.crypto.tunnelcrypto import CryptoException, TunnelCrypto
from Tribler.community.tunnel.routing import Circuit, Hop, RelayRoute
from Tribler.community.tunnel.tunnel_community import (TunnelSettings, TunnelExitSocket, CircuitRequestCache,
                                                       PingRequestCache)
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
    @inlineCallbacks
    def test_send_to_destination_ip(self):
        # This test checks if the ip address can be resolved when a destination object
        # is set and is_valid_address returns true.
        # Will result in an exception as self.transport is not initialized.
        # Which is catched by the try except in on_ip_address.
        circuit_id = 1337
        sock_addr = "127.0.0.1"
        exit_tunnel = TunnelExitSocket(circuit_id, self.tunnel_community, sock_addr, False)
        self.tunnel_community.exit_sockets[circuit_id] = exit_tunnel
        exit_tunnel.ips[("127.0.0.1", 8080)] = -1
        data = "ffffffff".decode("HEX") + "1" * 25
        exit_tunnel.sendto(data, ("127.0.0.1", 8080))
        res = yield exit_tunnel.close()
        returnValue(res)

    @deferred(timeout=5)
    @inlineCallbacks
    def test_send_to_ip_deferred(self):
        # This test checks if the ip address can be resolved when a destination object
        # is set and is_valid_address returns false.
        # Which will be cancelled by the close() function being called immediately.

        circuit_id = 1337
        sock_addr = "127.0.0.1"
        exit_tunnel = TunnelExitSocket(circuit_id, self.tunnel_community, sock_addr, False)
        self.tunnel_community.exit_sockets[circuit_id] = exit_tunnel
        exit_tunnel.ips[("localhost", -1)] = -1
        data = "ffffffff".decode("HEX") + "1" * 25
        exit_tunnel.sendto(data, ("localhost", -1))
        value = yield exit_tunnel.close()
        returnValue(value)

    def test_increase_bytes_sent_error_branch(self):
        self.assertRaises(TypeError, self.tunnel_community.increase_bytes_sent, 1, 1)

    def test_increase_bytes_received_error_branch(self):
        self.assertRaises(TypeError, self.tunnel_community.increase_bytes_received, 1, 1)

    def test_on_data_invalid_encoding(self):
        """
        When on_data receives an invalid encryption, crypto_in() should throw a CryptoException.
        """
        # Prepare crypto and settings
        tunnel_crypto = object.__new__(TunnelCrypto)
        self.tunnel_community.settings = TunnelSettings()
        # Register a valid circuit
        circuit = Circuit(42L)
        hop = Hop(tunnel_crypto.generate_key(u"curve25519"))
        hop.session_keys = tunnel_crypto.generate_session_keys("1234")
        circuit.add_hop(hop)
        self.tunnel_community.circuits[42] = circuit

        # Encode data with a truncated encrypted string (empty in this case)
        packet = TunnelConversion.encode_data(42, ("127.0.0.1", 1337), ("127.0.0.1", 1337), "")

        # Simulate on_data()
        _, encrypted = TunnelConversion.split_encrypted_packet(packet, u"data")
        self.assertRaises(CryptoException, self.tunnel_community.crypto_in, 42, encrypted, is_data=True)

    @blocking_call_on_reactor_thread
    def test_valid_member_on_tunnel_remove(self):
        """
        Notifications of NTFY_TUNNEL NTFY_REMOVE should report candidates with valid member associations
        """
        class MockNotifier(object):

            def __init__(self):
                self.candidate = None
                self.called = False

            def notify(self, subject, change_type, tunnel, candidate):
                self.called = True
                self.candidate = candidate

        # Prepare crypto
        tunnel_crypto = object.__new__(TunnelCrypto)
        # Register mock notifier
        self.tunnel_community.notifier = MockNotifier()
        # Register a valid circuit
        circuit = Circuit(42L)
        circuit.first_hop = ("127.0.0.1", 1337)
        hop = Hop(tunnel_crypto.generate_key(u"curve25519").pub())
        circuit.add_hop(hop)
        # Register the first hop with dispersy and the community
        circuit.mid = self.tunnel_community.dispersy.get_member(public_key=hop.node_public_key).mid.encode("HEX")
        self.tunnel_community.create_or_update_walkcandidate(circuit.first_hop, circuit.first_hop, circuit.first_hop,
                                                             True, u'unknown')
        self.tunnel_community.circuits[42] = circuit

        # Remove the circuit, causing the notification
        self.tunnel_community.remove_circuit(42)

        self.assertTrue(self.tunnel_community.notifier.called)
        self.assertNotEqual(self.tunnel_community.notifier.candidate, None)
        self.assertNotEqual(self.tunnel_community.notifier.candidate.get_member(), None)

    @blocking_call_on_reactor_thread
    def test_reconstruct_candidate_on_tunnel_remove(self):
        """
        Notifications of NTFY_TUNNEL NTFY_REMOVE should report candidates even though they are no longer tracked

        The notification should still have a valid Candidate object for the reference of third parties.
        For example, Dispersy might determine a Candidate is no longer needed for the TunnelCommunity, but the
        MultiChainCommunity will still be interested in the Candidate object tied to a removed circuit.
        """

        class MockNotifier(object):
            def __init__(self):
                self.candidate = None
                self.called = False

            def notify(self, subject, change_type, tunnel, candidate):
                self.called = True
                self.candidate = candidate

        # Prepare crypto
        tunnel_crypto = object.__new__(TunnelCrypto)
        # Register mock notifier
        self.tunnel_community.notifier = MockNotifier()
        # Register a valid circuit
        circuit = Circuit(42L)
        circuit.first_hop = ("127.0.0.1", 1337)
        hop = Hop(tunnel_crypto.generate_key(u"curve25519").pub())
        circuit.add_hop(hop)
        # Register the first hop with dispersy and the community
        circuit.mid = self.tunnel_community.dispersy.get_member(public_key=hop.node_public_key).mid.encode("HEX")
        self.tunnel_community.create_or_update_walkcandidate(circuit.first_hop, circuit.first_hop, circuit.first_hop,
                                                             True, u'unknown')
        self.tunnel_community.circuits[42] = circuit

        # Simulate a candidate cleanup
        self.tunnel_community.remove_candidate(circuit.first_hop)

        # Remove the circuit, causing the notification
        self.tunnel_community.remove_circuit(42)

        self.assertTrue(self.tunnel_community.notifier.called)
        self.assertNotEqual(self.tunnel_community.notifier.candidate, None)

    @blocking_call_on_reactor_thread
    def test_reconstruct_candidate_on_relay_remove(self):
        """
        Notifications of NTFY_TUNNEL NTFY_REMOVE should report candidates even though they are no longer tracked

        The notification should still have a valid Candidate object for the reference of third parties.
        For example, Dispersy might determine a Candidate is no longer needed for the TunnelCommunity, but the
        MultiChainCommunity will still be interested in the Candidate object tied to a removed circuit.
        """

        class MockNotifier(object):
            def __init__(self):
                self.candidate = None
                self.called = False

            def notify(self, subject, change_type, tunnel, candidate):
                self.called = True
                self.candidate = candidate

        # Prepare crypto
        tunnel_crypto = object.__new__(TunnelCrypto)
        # Register mock notifier
        self.tunnel_community.notifier = MockNotifier()
        # Register a valid circuit
        circuit = Circuit(42L)
        circuit.first_hop = ("127.0.0.1", 1337)
        hop = Hop(tunnel_crypto.generate_key(u"curve25519").pub())
        circuit.add_hop(hop)
        # Register the first hop with dispersy and the community
        circuit.mid = self.tunnel_community.dispersy.get_member(public_key=hop.node_public_key).mid.encode("HEX")
        self.tunnel_community.create_or_update_walkcandidate(circuit.first_hop, circuit.first_hop,
                                                             circuit.first_hop,
                                                             True, u'unknown')
        self.tunnel_community.circuits[42] = circuit
        #Register a RelayRoute
        self.tunnel_community.relay_from_to[circuit.circuit_id] = RelayRoute(circuit.circuit_id,
                                                                             circuit.first_hop,
                                                                             mid=circuit.mid)

        # Simulate a candidate cleanup
        self.tunnel_community.remove_candidate(circuit.first_hop)

        # Remove the circuit, causing the notification
        self.tunnel_community.remove_relay(42)

        self.assertTrue(self.tunnel_community.notifier.called)
        self.assertNotEqual(self.tunnel_community.notifier.candidate, None)
