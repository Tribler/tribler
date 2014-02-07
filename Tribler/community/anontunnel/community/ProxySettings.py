from random import randint
from Tribler.community.anontunnel import extendstrategies, selectionstrategies, lengthstrategies
from Tribler.community.anontunnel.community import CircuitReturnFactory
from Tribler.community.anontunnel.crypto import DefaultCrypto

__author__ = 'Chris'


class ProxySettings:
    def __init__(self):
        length = randint(0, 3)

        self.max_circuits = 1 if length == 0 else 4
        self.extend_strategy = extendstrategies.NeighbourSubset
        self.select_strategy = selectionstrategies.RoundRobinSelectionStrategy(self.max_circuits)
        self.length_strategy = lengthstrategies.ConstantCircuitLengthStrategy(length)
        self.return_handler_factory = CircuitReturnFactory()
        self.crypto = DefaultCrypto()
