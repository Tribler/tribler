import random
import logging

logger = logging.getLogger(__name__)

r = random.Random()

__author__ = 'chris'
class SelectionStrategy:
    
    def __init__(self):
        pass

    def select(self, circuits_to_select_from):
        pass


class RoundRobinSelectionStrategy(SelectionStrategy):
    def __init__(self, min_population_size):
        SelectionStrategy.__init__(self)
        self.min_population_size = min_population_size
        self.index = -1

    def can_select(self, circuits_to_select_from):
        if len(circuits_to_select_from) < self.min_population_size:
            return False

        return True

    def select(self, circuits_to_select_from):
        if not self.can_select(circuits_to_select_from):
            raise ValueError("At least %d circuits are needed before we select a tunnel" % (self.min_population_size,))

        self.index = (self.index + 1) % len(circuits_to_select_from)
        return circuits_to_select_from[self.index]


class RandomSelectionStrategy(SelectionStrategy):
    
    def __init__(self, min_population_size):
        SelectionStrategy.__init__(self)
        self.min_population_size = min_population_size

    def can_select(self, circuits_to_select_from):
        if len(circuits_to_select_from) < self.min_population_size:
            return False

        return True

    def select(self, circuits_to_select_from):
        if len(circuits_to_select_from) < self.min_population_size:
            raise ValueError("At least %d circuits are needed before we select a tunnel" % (self.min_population_size,))

        circuit = r.choice(circuits_to_select_from)
        return circuit


class LengthSelectionStrategy(SelectionStrategy):
    
    def __init__(self, min, max, random=True):
        self.min = int(min)
        self.max = int(max)
        self.random = True if random else False

    def can_select(self, circuits_to_select_from):
        logger.debug("Trying to select from {} with length between {} and {}".format([len(c.hops) for c in circuits_to_select_from], self.min, self.max))
        candidates = [c for c in circuits_to_select_from if self.min <= len(c.hops) <= self.max]

        return len(candidates) > 0

    def select(self, circuits_to_select_from):
        if not self.can_select(circuits_to_select_from):
            logger.error("ERROR select from {} with length between {} and {}".format([len(c.hops) for c in circuits_to_select_from], self.min, self.max))

            raise ValueError("No circuits meeting criteria")

        candidates = [c for c in circuits_to_select_from if self.min <= len(c.hops) <= self.max]

        if self.random:
            return r.choice(candidates)
        else:
            return candidates[0]