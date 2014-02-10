from random import randint

__author__ = 'chris'


class CircuitLengthStrategy(object):
    def __init__(self):
        pass

    def circuit_length(self):
        raise NotImplementedError()


class RandomCircuitLengthStrategy(CircuitLengthStrategy):
    def __init__(self, minimum_length, maximum_length):
        super(RandomCircuitLengthStrategy, self).__init__()
        self.min = int(minimum_length)
        self.max = int(maximum_length)

    def circuit_length(self):
        return randint(self.min, self.max)


class ConstantCircuitLengthStrategy(CircuitLengthStrategy):
    def __init__(self, desired_length):
        super(ConstantCircuitLengthStrategy, self).__init__()
        self.desired_length = int(desired_length)

    def circuit_length(self):
        return self.desired_length