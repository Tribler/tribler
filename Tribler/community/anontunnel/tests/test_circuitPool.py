from unittest import TestCase
from Tribler.community.anontunnel.routing import CircuitPool, Circuit

__author__ = 'Chris'


class TestCircuitPool(TestCase):
    def setUp(self):
        self.pool = CircuitPool(5, 'test pool')

    def test_on_break_circuit(self):
        for i in range(1, 5):
            circuit = Circuit(0, 0)
            self.pool.fill(circuit)
            self.pool.on_break_circuit(circuit)
            self.assertNotIn(circuit, self.pool.circuits)
            self.assertNotIn(circuit, self.pool.available_circuits)

    def test_lacking(self):
        for i in range(1, 5):
            circuit = Circuit(0, 0)
            self.pool.fill(circuit)

            self.assertEqual(self.pool.lacking, 5-i)

    def test_available_circuits(self):
        circuits = [Circuit(0, 0) for _ in range(5)]

        for circuit in circuits:
            self.pool.fill(circuit)
            self.assertIn(circuit, self.pool.available_circuits)
            self.pool.remove_circuit(circuit)
            self.assertNotIn(circuit, self.pool.available_circuits)

    def test_remove_circuit(self):
        circuits = [Circuit(0, 0) for _ in range(5)]

        for circuit in circuits:
            self.pool.fill(circuit)
            self.assertIn(circuit, self.pool.circuits)
            self.pool.remove_circuit(circuit)
            self.assertNotIn(circuit, self.pool.circuits)

    def test_fill(self):
        for i in range(1, 5):
            circuit = Circuit(0, 0)
            self.pool.fill(circuit)

            self.assertIn(circuit, self.pool.circuits)
            self.assertIn(circuit, self.pool.available_circuits)

    def test_deallocate(self):
        circuits = [Circuit(0, 0) for _ in range(5)]

        for circuit in circuits:
            self.pool.fill(circuit)

        for i in range(1, 5):
            circuit = self.pool.allocate()
            self.assertIn(circuit, self.pool.circuits)
            self.assertNotIn(circuit, self.pool.available_circuits)
            self.pool.deallocate(circuit)
            self.assertIn(circuit, self.pool.available_circuits)

    def test_allocate(self):
        circuits = [Circuit(0, 0) for _ in range(5)]

        for circuit in circuits:
            self.pool.fill(circuit)

        for i in range(1, 5):
            circuit = self.pool.allocate()
            self.assertIn(circuit, self.pool.circuits)
            self.assertNotIn(circuit, self.pool.available_circuits)