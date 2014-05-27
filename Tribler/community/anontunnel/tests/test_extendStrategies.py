from unittest import TestCase
from Tribler.community.anontunnel.extendstrategies import TrustThyNeighbour
from Tribler.community.anontunnel.globals import MESSAGE_EXTEND, \
    CIRCUIT_STATE_BROKEN
from Tribler.community.anontunnel.payload import ExtendMessage
from Tribler.community.anontunnel.routing import Circuit, Hop
from Tribler.dispersy.candidate import Candidate

__author__ = 'chris'


class ProxyMock:
    def __init__(self):
        self.message = None

    def send_message(self, *args):
        self.message = args


#noinspection PyTypeChecker,PyTypeChecker
class TestTrustThyNeighbour(TestCase):
    def setUp(self):
        self.proxy = ProxyMock()

    def test_extend_ready_circuit(self):
        circuit_candidate = Candidate(("127.0.0.1", 1000), False)
        circuit = Circuit(1, 1, circuit_candidate)
        circuit.add_hop(Hop(None))

        es = TrustThyNeighbour(self.proxy, circuit)
        self.assertRaises(AssertionError, es.extend)

    def test_extend_broken_circuit(self):
        circuit_candidate = Candidate(("127.0.0.1", 1000), False)
        circuit = Circuit(1, 1, circuit_candidate)

        # Break circuit
        circuit.destroy()
        self.assertEqual(circuit.state, CIRCUIT_STATE_BROKEN)

        es = TrustThyNeighbour(self.proxy, circuit)
        self.assertRaises(AssertionError, es.extend)

    def test_extend_extending_circuit(self):
        circuit_candidate = Candidate(("127.0.0.1", 1000), False)
        circuit = Circuit(1, 2, circuit_candidate)
        es = TrustThyNeighbour(self.proxy, circuit)
        es.extend()

        self.assertIsInstance(self.proxy.message, tuple)

        candidate, circuit_id, message_type, message = self.proxy.message

        self.assertEqual(candidate, circuit.first_hop,
                         "Candidate should be first hop of circuit")
        self.assertEqual(circuit_id, circuit.circuit_id,
                         "Circuit_id should be circuit's id")
        self.assertEqual(message_type, MESSAGE_EXTEND,
                         "Send message should be an extend type")
        self.assertIsInstance(message, ExtendMessage)
