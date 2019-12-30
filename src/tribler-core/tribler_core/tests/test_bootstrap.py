from binascii import unhexlify

from ipv8.keyvault.crypto import ECCrypto

from tribler_core.modules.bootstrap import Bootstrap
from tribler_core.tests.tools.base_test import MockObject
from tribler_core.tests.tools.test_as_server import TestAsServer
from tribler_core.utilities.utilities import succeed


class FakeDHT(object):

    def connect_peer(self, mid):
        matched_node = MockObject()
        matched_node.mid = mid
        matched_node.public_key = ECCrypto().generate_key("low").pub()

        nearby_node = MockObject()
        nearby_node.mid = unhexlify('b' * 20)
        nearby_node.public_key = ECCrypto().generate_key("low").pub()

        return succeed([matched_node, nearby_node])


class TestBootstrapDownload(TestAsServer):

    async def setUp(self):
        await super(TestBootstrapDownload, self).setUp()
        self.bootstrap = Bootstrap(self.temporary_directory(), dht=FakeDHT())

    async def test_load_and_fetch_bootstrap_peers(self):
        # Before bootstrap download
        nodes = await self.bootstrap.fetch_bootstrap_peers()
        self.assertEqual(nodes, {})

        # Assuming after bootstrap download
        self.bootstrap.download = MockObject()
        self.bootstrap.download.get_peerlist = lambda: [{'id': 'a' * 20}]

        await self.bootstrap.fetch_bootstrap_peers()

        # Assuming DHT returns two peers for bootstrap download
        self.assertIsNotNone(self.bootstrap.bootstrap_nodes['a' * 20])
        self.assertIsNotNone(self.bootstrap.bootstrap_nodes['b' * 20])
