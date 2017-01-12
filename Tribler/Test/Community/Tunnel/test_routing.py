from Tribler.Test.Core.base_test import TriblerCoreTest
from Tribler.community.tunnel.hidden_community import HiddenTunnelCommunity
from Tribler.community.tunnel.routing import Circuit


class TestRouting(TriblerCoreTest):

    def test_circuit_tunnel_data(self):
        """
        Test whether the right methods are called when tunneling data over a circuit
        """
        proxy = HiddenTunnelCommunity.__new__(HiddenTunnelCommunity)
        proxy.stats = {'bytes_up': 0}
        proxy.send_data = lambda *_: 3
        circuit = Circuit(1234L, 3, proxy=proxy, first_hop=("1.2.3.5", 1235))
        circuit.tunnel_data(("1.2.3.4", 1234), 'abcd')
        proxy.send_data = lambda *_: 0
        circuit.tunnel_data(("1.2.3.4", 1234), 'abcd')
        self.assertEqual(proxy.stats['bytes_up'], 3)
