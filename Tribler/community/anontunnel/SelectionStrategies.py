from random import choice

__author__ = 'chris'


class SelectionStrategy:
    def __init__(self):
        pass

    def select(self, circuits_to_select_from):
        pass


class RandomSelectionStrategy(SelectionStrategy):
    def __init__(self, min_population_size):
        SelectionStrategy.__init__(self)
        self.min_population_size = min_population_size
        self.previous = None

    def try_select(self, circuits_to_select_from):
        if len(circuits_to_select_from) < self.min_population_size:
            raise ValueError("At least %d circuits are needed before we select a tunnel" % (self.min_population_size,))

    def select(self, circuits_to_select_from):
        if len(circuits_to_select_from) < self.min_population_size:
            raise ValueError("At least %d circuits are needed before we select a tunnel" % (self.min_population_size,))

        circuit = choice(circuits_to_select_from)

        while circuit is self.previous:
            circuit = choice(circuits_to_select_from)

        self.previous = circuit

        return circuit



class LengthSelectionStrategy(SelectionStrategy):
    def __init__(self, min, max, random=True):
        self.min = int(min)
        self.max = int(max)
        self.random = True if random else False

    def try_select(self, circuits_to_select_from):
        candidates = [c for c in circuits_to_select_from if self.min <= len(c.hops) <= self.max]

        if len(candidates) == 0:
            raise ValueError()

    def select(self, circuits_to_select_from):
        candidates = [c for c in circuits_to_select_from if self.min <= len(c.hops) <= self.max]

        if self.random:
            return choice(candidates)
        else:
            return candidates[0]