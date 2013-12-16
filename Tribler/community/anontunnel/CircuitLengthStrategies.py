from random import randint

__author__ = 'chris'


class CircuitLengthStrategy(object):
    def __init__(self):
        pass

    def circuit_length(self):
        raise NotImplementedError()


class RandomCircuitLengthStrategy(CircuitLengthStrategy):
    def __init__(self, min, max):
        self.min = int(min)
        self.max = int(max)

    def circuit_length(self):
        return randint(self.min, self.max)


class ConstantCircuitLengthStrategy(CircuitLengthStrategy):
    def __init__(self, desired_length):
        self.desired_length = int(desired_length)

    def circuit_length(self):
        return self.desired_length