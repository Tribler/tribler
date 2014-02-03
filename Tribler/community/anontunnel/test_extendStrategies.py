from unittest import TestCase
from Tribler.community.anontunnel.extendstrategies import TrustThyNeighbour
from Tribler.community.anontunnel.community import Circuit
from Tribler.community.anontunnel.globals import MESSAGE_EXTEND, CIRCUIT_STATE_BROKEN
from Tribler.community.anontunnel.payload import ExtendMessage
from Tribler.dispersy.candidate import Candidate

__author__ = 'chris'

class ProxyMock:
    def __init__(self):
        self.message = None

    def send_message(self, *args):
        self.message = args

class TestTrustThyNeighbour(TestCase):
    def setUp(self):
        self.proxy = ProxyMock()

    def test_extend_ready_circuit(self):
        circ_candidate = Candidate(("127.0.0.1", 1000), False)
        circuit = Circuit(1,1, circ_candidate)
        es = TrustThyNeighbour(self.proxy, circuit)
        self.assertRaises(AssertionError, es.extend)

    def test_extend_broken_circuit(self):
        circ_candidate = Candidate(("127.0.0.1", 1000), False)
        circuit = Circuit(1,1, circ_candidate)

        # Break circuit
        circuit.hops = None
        self.assertEqual(circuit.state, CIRCUIT_STATE_BROKEN)

        es = TrustThyNeighbour(self.proxy, circuit)
        self.assertRaises(AssertionError, es.extend)

    def test_extend_extending_circuit(self):
        circ_candidate = Candidate(("127.0.0.1", 1000), False)
        circuit = Circuit(1,2, circ_candidate)
        es = TrustThyNeighbour(self.proxy, circuit)
        es.extend()

        self.assertIsInstance(self.proxy.message, tuple)

        candidate, circuit_id, message_type, message = self.proxy.message

        self.assertEqual(candidate, circuit.candidate, "Candidate should be first hop of circuit")
        self.assertEqual(circuit_id, circuit.circuit_id, "Circuit_id should be circuit's id")
        self.assertEqual(message_type, MESSAGE_EXTEND, "Send message should be an extend type")
        self.assertIsInstance(message, ExtendMessage)
