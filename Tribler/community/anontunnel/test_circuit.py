from unittest import TestCase
from Tribler.community.anontunnel.community import Circuit
from Tribler.community.anontunnel.globals import CIRCUIT_STATE_EXTENDING, CIRCUIT_STATE_READY
from Tribler.dispersy.candidate import Candidate

__author__ = 'chris'


class TestCircuit(TestCase):
    def test_online(self):
        candidate = Candidate(("127.0.0.1", 1000), False)

        circuit = Circuit(1, 2, candidate)
        self.assertFalse(circuit.online, "Circuit should not be online when goal hops not reached")

        circuit = Circuit(1, 1, candidate)
        self.assertTrue(circuit.online, "Single hop circuit with candidate should always be online")

        circuit = Circuit(0)
        self.assertTrue(circuit.online, "Zero hop circuit should always be online")

    def test_state(self):
        candidate = Candidate(("127.0.0.1", 1000), False)

        circuit = Circuit(1,2, candidate)
        self.assertEqual(circuit.state, CIRCUIT_STATE_EXTENDING, "Circuit should be EXTENDING when goal hops not reached")

        circuit = Circuit(1,1, candidate)
        self.assertEqual(circuit.state, CIRCUIT_STATE_READY, "Single hop circuit with candidate should always READY")

        circuit = Circuit(0)
        self.assertEqual(circuit.state, CIRCUIT_STATE_READY, "Zero hop circuit should always be READY")
