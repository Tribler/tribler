import logging.config
import os
import time

from mock import Mock
from twisted.internet import reactor
from twisted.internet.threads import blockingCallFromThread

from Tribler.Test.test_as_server import TestAsServer
from Tribler.community.tunnel import exitstrategies
from Tribler.community.tunnel.tunnel_community import TunnelCommunity, TunnelSettings
from Tribler.community.tunnel.crypto.tunnelcrypto import NoCrypto
from Tribler.community.tunnel.events import TunnelObserver
from Tribler.community.tunnel import (MESSAGE_CREATED, MESSAGE_CREATE, CIRCUIT_STATE_READY,
                                      CIRCUIT_STATE_EXTENDING, CIRCUIT_STATE_BROKEN,
                                      MESSAGE_EXTEND, MESSAGE_PONG)
from Tribler.community.tunnel.payload import (CreateMessage, CreatedMessage, ExtendedMessage, ExtendMessage,
                                              DataMessage, PingMessage, PongMessage)
from Tribler.community.tunnel.routing import Circuit
from Tribler.dispersy.candidate import WalkCandidate, CANDIDATE_ELIGIBLE_DELAY
from Tribler.dispersy.endpoint import NullEndpoint
from Tribler.dispersy.util import call_on_reactor_thread


__author__ = 'Chris'

logging.config.fileConfig(
    os.path.dirname(os.path.realpath(__file__)) + "/../logger.conf")


class DummyEndpoint(NullEndpoint):

    def send_simple(self, *args):
        pass


class TestProxyCommunity(TestAsServer):

    @call_on_reactor_thread
    def setUp(self):
        super(TestProxyCommunity, self).setUp()
        self.__candidate_counter = 0
        self.dispersy = self.session.lm.dispersy

        dispersy = self.dispersy

        keypair = dispersy.crypto.generate_key(u"curve25519")
        dispersy_member = dispersy.get_member(private_key=dispersy.crypto.key_to_bin(keypair))

        settings = TunnelSettings()
        settings.crypto = NoCrypto()

        self.community = dispersy.define_auto_load(TunnelCommunity, dispersy_member, (settings, None), load=True)[0]
        exit_strategy = exitstrategies.DefaultExitStrategy(self.session.lm.rawserver, self.community)
        self.community.observers.append(exit_strategy)

        ''' :type : ProxyCommunity '''

    def setUpPreSession(self):
        super(TestProxyCommunity, self).setUpPreSession()
        self.config.set_dispersy(True)

    @call_on_reactor_thread
    def __create_walk_candidate(self):
        self.__candidate_counter += 1
        wan_address = ("8.8.8.{0}".format(self.__candidate_counter), self.__candidate_counter)
        lan_address = ("0.0.0.0", 0)
        candidate = WalkCandidate(wan_address, False, lan_address, wan_address, u'unknown')

        key = self.dispersy.crypto.generate_key(u"curve25519")
        member = self.dispersy.get_member(public_key=self.dispersy.crypto.key_to_bin(key.pub()))
        candidate.associate(member)

        now = time.time()
        candidate.walk(now - CANDIDATE_ELIGIBLE_DELAY)
        candidate.walk_response(now)
        return candidate

    def test_on_create(self):
        create_sender = self.__create_walk_candidate()

        create_message = CreateMessage()
        circuit_id = 1337

        self.community.send_message = send_message = Mock()
        self.community.on_create(circuit_id, create_sender, create_message)

        args, keyargs = send_message.call_args

        self.assertEqual(create_sender, keyargs['destination'])
        self.assertEqual(circuit_id, keyargs['circuit_id'])
        self.assertEqual(MESSAGE_CREATED, keyargs['message_type'])
        self.assertIsInstance(keyargs['message'], CreatedMessage)

    def test_create_circuit(self):
        create_sender = self.__create_walk_candidate()

        self.assertRaises(ValueError, self.community.create_circuit, create_sender, 0)

        self.community.send_message = send_message = Mock()

        hops = 1
        circuit = self.community.create_circuit(create_sender, hops)

        # Newly created circuit should be stored in circuits dict
        self.assertIsInstance(circuit, Circuit)
        self.assertEqual(create_sender, circuit.first_hop)
        self.assertEqual(hops, circuit.goal_hops)
        self.assertIn(circuit.circuit_id, self.community.circuits)
        self.assertEqual(circuit, self.community.circuits[circuit.circuit_id])
        self.assertEqual(CIRCUIT_STATE_EXTENDING, circuit.state)

        # We must have sent a CREATE message to the candidate in question
        args, kwargs = send_message.call_args
        destination, reply_circuit, message_type, created_message = args
        self.assertEqual(circuit.circuit_id, reply_circuit)
        self.assertEqual(create_sender, destination)
        self.assertEqual(MESSAGE_CREATE, message_type)
        self.assertIsInstance(created_message, CreateMessage)

    def test_on_created(self):
        first_hop = self.__create_walk_candidate()
        circuit = self.community.create_circuit(first_hop, 1)

        self.community.on_created(circuit.circuit_id, first_hop, CreatedMessage([]))
        self.assertEqual(CIRCUIT_STATE_READY, circuit.state)

    def test_on_extended(self):
        # 2 Hop - should fail due to no extend candidates
        first_hop = self.__create_walk_candidate()
        circuit = self.community.create_circuit(first_hop, 2)

        result = self.community.on_created(circuit.circuit_id, first_hop, CreatedMessage([]))
        self.assertFalse(result)
        self.assertEqual(CIRCUIT_STATE_BROKEN, circuit.state)

        # 2 Hop - should succeed
        second_hop = self.__create_walk_candidate()

        public_bin = second_hop.get_member().public_key
        key = second_hop.get_member()._ec

        candidate_list = []
        candidate_list.append(self.community.crypto.key_to_bin(key))
        circuit = self.community.create_circuit(first_hop, 2)

        self.community.send_message = send_message = Mock()

        result = self.community.on_created(circuit.circuit_id, first_hop, CreatedMessage(candidate_list))
        self.assertTrue(result)

        # ProxyCommunity should send an EXTEND message with the hash of second_hop's pub-key
        args, kwargs = send_message.call_args
        circuit_candidate, circuit_id, message_type, message = args

        self.assertEqual(first_hop, circuit_candidate)
        self.assertEqual(circuit.circuit_id, circuit_id)
        self.assertEqual(MESSAGE_EXTEND, message_type)
        self.assertIsInstance(message, ExtendMessage)
        self.assertEqual(message.extend_with, public_bin)

        # Upon reception of the ON_EXTENDED the circuit should reach it full 2-hop length and thus be ready for use
        result = self.community.on_extended(circuit.circuit_id, first_hop, ExtendedMessage("", []))
        self.assertTrue(result)
        self.assertEqual(CIRCUIT_STATE_READY, circuit.state)

    def test_remove_circuit(self):
        first_hop = self.__create_walk_candidate()
        circuit = self.community.create_circuit(first_hop, 1)

        self.assertIn(circuit.circuit_id, self.community.circuits)
        self.community.remove_circuit(circuit.circuit_id)
        self.assertNotIn(circuit, self.community.circuits)

    def test_on_data(self):
        first_hop = self.__create_walk_candidate()
        circuit = self.community.create_circuit(first_hop, 1)
        self.community.on_created(circuit.circuit_id, first_hop, CreatedMessage([]))

        payload = "Hello world"
        origin = ("google.com", 80)
        data_message = DataMessage(None, payload, origin=origin)

        observer = TunnelObserver()
        observer.on_incoming_from_tunnel = on_incoming_from_tunnel = Mock()
        self.community.observers.append(observer)

        # Its on our own circuit so it should trigger the on_incoming_from_tunnel event
        self.community.on_data(circuit.circuit_id, first_hop, data_message)
        on_incoming_from_tunnel.assert_called_with(self.community, circuit, origin, payload)

        # Not our own circuit so we need to exit it
        destination = ("google.com", 80)
        exit_message = DataMessage(destination, payload, origin=None)
        observer.on_exiting_from_tunnel = on_exiting_from_tunnel = Mock()
        self.community.on_data(1337, first_hop, exit_message)
        on_exiting_from_tunnel.assert_called_with(1337, first_hop, destination, payload)

    def test_on_extend(self):
        # We mimick the intermediary hop ( ORIGINATOR - INTERMEDIARY - NODE_TO_EXTEND_ORIGINATORS_CIRCUIT_WITH )
        originator = self.__create_walk_candidate()
        node_to_extend_with = self.__create_walk_candidate()
        originator_circuit_id = 1337

        extend_pub_key = node_to_extend_with.get_member()._ec
        extend_pub_key = self.dispersy.crypto.key_to_bin(extend_pub_key)

        # make sure our node_to_extend_with comes up when yielding verified candidates
        blockingCallFromThread(reactor, self.community.add_candidate, node_to_extend_with)
        self.assertIn(node_to_extend_with, self.community._candidates.itervalues())

        self.community.send_message = send_message = Mock()
        self.community.on_create(originator_circuit_id, originator, CreateMessage())

        # Check whether we are sending node_to_extend_with in the CreatedMessage reply
        args, kwargs = send_message.call_args
        created_message = kwargs['message']
        candidate_dict = created_message.candidate_list
        self.assertIsInstance(created_message, CreatedMessage)
        self.assertIn(extend_pub_key, candidate_dict)

        self.community.on_extend(originator_circuit_id, originator, ExtendMessage(extend_pub_key))

        # Check whether we are sending a CREATE to node_to_extend_with
        args, kwargs = send_message.call_args
        create_destination, circuit_id, message_type, message = args
        self.assertEqual(node_to_extend_with, create_destination)
        self.assertEqual(MESSAGE_CREATE, message_type)
        self.assertIsInstance(message, CreateMessage)

        # Check whether the routing table has been updated
        relay_from_originator = (originator.sock_addr, originator_circuit_id)
        relay_from_endpoint = (node_to_extend_with.sock_addr, circuit_id)

        self.assertIn(relay_from_originator, self.community.relay_from_to)
        self.assertIn(relay_from_endpoint, self.community.relay_from_to)

    def test_on_pong(self):
        first_hop = self.__create_walk_candidate()
        circuit = self.community.create_circuit(first_hop, 1)
        self.community.on_created(circuit.circuit_id, first_hop, CreatedMessage({}))

        result = self.community.on_pong(circuit.circuit_id, first_hop, PongMessage())
        self.assertFalse(result, "Cannot handle a pong when we never sent a PING")

        self.community.create_ping(first_hop, circuit)

        # Check whether the circuit last incoming time is correct after the pong
        circuit.last_incoming = 0
        result = self.community.on_pong(circuit.circuit_id, first_hop, PongMessage())
        self.assertTrue(result)

        self.assertAlmostEqual(circuit.last_incoming, time.time(), delta=0.5)

    def test_on_ping(self):
        circuit_id = 1337
        first_hop = self.__create_walk_candidate()
        self.community.add_candidate(first_hop)

        self.community.on_create(circuit_id, first_hop, CreateMessage())

        self.community.send_message = send_message = Mock()
        self.community.on_ping(circuit_id, first_hop, PingMessage())

        # Check whether we responded with a pong
        args, kwargs = send_message.call_args

        self.assertEqual(first_hop, kwargs['destination'])
        self.assertEqual(circuit_id, kwargs['circuit_id'])
        self.assertEqual(MESSAGE_PONG, kwargs['message_type'])
        self.assertIsInstance(kwargs['message'], PongMessage)
