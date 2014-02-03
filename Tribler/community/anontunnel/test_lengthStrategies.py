from unittest import TestCase
from Tribler.community.anontunnel.lengthstrategies import RandomCircuitLengthStrategy, ConstantCircuitLengthStrategy

__author__ = 'chris'


class TestRandomCircuitLengthStrategy(TestCase):
    def test_circuit_length(self):
        ls = RandomCircuitLengthStrategy(3, 100)
        self.assertGreaterEqual(ls.circuit_length(), 3, "Should be at least 3")
        self.assertLessEqual(ls.circuit_length(), 100, "Should be at least 100")

        ls = RandomCircuitLengthStrategy(3, 3)
        self.assertEqual(ls.circuit_length(), 3, "Should be 3 exactly")


class TestConstantCircuitLengthStrategy(TestCase):
    def test_circuit_length(self):
        ls = ConstantCircuitLengthStrategy(42)
        self.assertEqual(ls.circuit_length(), 42, "Should be 42 exactly")
