from random import randint
from unittest import TestCase

from Tribler.community.anontunnel.selectionstrategies import LengthSelectionStrategy, RandomSelectionStrategy
from Tribler.community.anontunnel.community import Circuit
from Tribler.dispersy.candidate import Candidate


__author__ = 'chris'


class TestLengthSelectionStrategy(TestCase):
    def setUp(self):
        self.circuits = [self.__circuit(0), self.__circuit(1), self.__circuit(2), self.__circuit(3), self.__circuit(4)]

    @staticmethod
    def __circuit(hops):
        candidate = Candidate(("127.0.0.1", 1000), False)

        circuit = Circuit(randint(0, 1000), hops, candidate)
        circuit.hops = [candidate] * hops

        return circuit

    def test_select(self):
        cs = LengthSelectionStrategy(3, 3)
        self.assertEqual(cs.select(self.circuits), self.circuits[3])

        cs = LengthSelectionStrategy(0, 3)
        self.assertIn(cs.select(self.circuits), self.circuits[0:4])

        cs = LengthSelectionStrategy(1, 3)
        self.assertIn(cs.select(self.circuits), self.circuits[1:3])

        cs = LengthSelectionStrategy(5,10)
        self.assertRaises(ValueError, cs.select, self.circuits)

    def test_can_select(self):
        cs = LengthSelectionStrategy(3, 3)
        self.assertTrue(cs.can_select(self.circuits))

        cs = LengthSelectionStrategy(0, 3)
        self.assertTrue(cs.can_select(self.circuits))

        cs = LengthSelectionStrategy(1, 3)
        self.assertTrue(cs.can_select(self.circuits))

        cs = LengthSelectionStrategy(5,10)
        self.assertFalse(cs.can_select(self.circuits))



class TestRandomSelectionStrategy(TestCase):
    def setUp(self):
        self.circuits = [self.__circuit(1), self.__circuit(2), self.__circuit(3), self.__circuit(4)]

    @staticmethod
    def __circuit(hops):
        candidate = Candidate(("127.0.0.1", 1000), False)

        circuit = Circuit(randint(0, 1000), hops, candidate)
        circuit.hops = [candidate] * hops

        return circuit

    def test_try_select(self):
        cs = RandomSelectionStrategy(1)
        self.assertTrue(cs.can_select(self.circuits))
        self.assertFalse(cs.can_select([]))

    def test_select(self):
        cs = RandomSelectionStrategy(1)
        self.assertIsInstance(cs.select(self.circuits), Circuit)

        # Cannot select from empty list
        self.assertRaises(ValueError, cs.select, [])