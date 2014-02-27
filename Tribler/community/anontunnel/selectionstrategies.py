import random
import logging

__author__ = 'chris'


class SelectionStrategy:
    """
    Base class for selection strategies
    """
    def __init__(self):
        self._logger = logging.getLogger(__name__)

    def select(self, circuits_to_select_from):
        """
        Selects a circuit from a list of candidates
        @param list[Circuit] circuits_to_select_from: the circuits to pick from
        @rtype: Circuit
        """
        pass


class RoundRobin(SelectionStrategy):
    """
    Selects circuits in round robin fashion
    """
    def __init__(self):
        SelectionStrategy.__init__(self)
        self.index = -1

    def select(self, circuits_to_select_from):
        self.index = (self.index + 1) % len(circuits_to_select_from)
        return circuits_to_select_from[self.index]


class RandomSelectionStrategy(SelectionStrategy):
    """
    Strategy that selects a circuit at random
    """

    def select(self, circuits_to_select_from):
        circuit = random.choice(circuits_to_select_from)
        return circuit


class LengthSelectionStrategy(SelectionStrategy):
    """
    Selects a circuit which length is between the min and max given (inclusive)
    """
    def __init__(self, minimum_length, maximum_length, random_selection=True):
        SelectionStrategy.__init__(self)
        self.min = int(minimum_length)
        self.max = int(maximum_length)
        self.random = random_selection

    def select(self, circuits_to_select_from):
        candidates = [c for c in circuits_to_select_from if
                      self.min <= len(c.hops) <= self.max]

        if self.random:
            return random.choice(candidates)
        else:
            return candidates[0]