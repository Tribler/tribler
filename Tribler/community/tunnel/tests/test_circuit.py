import time

from unittest import TestCase

from Tribler.community.tunnel import CIRCUIT_STATE_READY, CIRCUIT_STATE_BROKEN
from Tribler.community.tunnel.routing import Circuit, Hop
from Tribler.dispersy.candidate import Candidate

__author__ = 'chris'


class TestCircuit(TestCase):

    def test_destroy(self):
        candidate = Candidate(("127.0.0.1", 1000), False)
        circuit = Circuit(1, 1, candidate)

        self.assertNotEqual(CIRCUIT_STATE_BROKEN, circuit.state,
                            "Newly created circuit should not be considered broken")
        circuit.destroy("Because we want to")
        self.assertEqual(CIRCUIT_STATE_BROKEN, circuit.state, "Destroyed circuit should be considered broken")

    def test_beat_heart(self):
        candidate = Candidate(("127.0.0.1", 1000), False)
        circuit = Circuit(1, 1, candidate)
        circuit.add_hop(Hop(None))

        circuit.beat_heart()
        self.assertAlmostEqual(time.time(), circuit.last_incoming,
                               delta=0.1, msg="Beat heart should update the last_incoming time")

    def test_state(self):
        candidate = Candidate(("127.0.0.1", 1000), False)

        circuit = Circuit(1, 2, candidate)
        self.assertNotEqual(
            CIRCUIT_STATE_READY, circuit.state,
            "Circuit should not be online when goal hops not reached")

        circuit = Circuit(1, 1, candidate)
        self.assertNotEqual(
            CIRCUIT_STATE_READY, circuit.state,
            "Single hop circuit without confirmed first hop should always be offline")

        circuit.add_hop(Hop(None))
        self.assertEqual(
            CIRCUIT_STATE_READY, circuit.state,
            "Single hop circuit with candidate should always be online")

        circuit = Circuit(0)
        self.assertEqual(CIRCUIT_STATE_READY, circuit.state,
                         "Zero hop circuit should always be online")
