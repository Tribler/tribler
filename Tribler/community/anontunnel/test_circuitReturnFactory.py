from unittest import TestCase
from Tribler.community.anontunnel.ConnectionHandlers.CircuitReturnHandler import ShortCircuitReturnHandler, CircuitReturnHandler
from Tribler.community.anontunnel.community import CircuitReturnFactory

__author__ = 'chris'


class TestCircuitReturnFactory(TestCase):
    def setUp(self):
        self.factory = CircuitReturnFactory()
        self.raw_server = object()
        self.proxy = object()

    def test_create_for_ciruit_zero(self):
        socket = self.factory.create(self.proxy, self.raw_server, 0, ('127.0.0.1', 1))
        self.assertIsInstance(socket, ShortCircuitReturnHandler, "For circuit zero, the ShortCircuitReturnHandler must be created")

    def test_create_for_real_circuit(self):
        socket = self.factory.create(self.proxy, self.raw_server, 0, ('127.0.0.1', 1))
        self.assertIsInstance(socket, CircuitReturnHandler, "For a real circuit, the CircuitReturnHandler must be created")

