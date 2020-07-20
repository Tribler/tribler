from binascii import unhexlify

from ipv8.keyvault.crypto import ECCrypto
from ipv8.util import succeed

import pytest

from tribler_core.modules.bootstrap import Bootstrap
from tribler_core.tests.tools.base_test import MockObject


@pytest.fixture
async def bootstrap(tmpdir):
    bootstrap = Bootstrap(tmpdir, dht=FakeDHT())
    yield bootstrap
    await bootstrap.shutdown()


class FakeDHT(object):

    def connect_peer(self, mid):
        matched_node = MockObject()
        matched_node.mid = mid
        matched_node.public_key = ECCrypto().generate_key("low").pub()

        nearby_node = MockObject()
        nearby_node.mid = unhexlify('b' * 20)
        nearby_node.public_key = ECCrypto().generate_key("low").pub()

        return succeed([matched_node, nearby_node])


@pytest.mark.asyncio
async def test_load_and_fetch_bootstrap_peers(bootstrap):
    # Before bootstrap download
    nodes = await bootstrap.fetch_bootstrap_peers()
    assert nodes == {}

    # Assuming after bootstrap download
    bootstrap.download = MockObject()
    bootstrap.download.get_peerlist = lambda: [{'id': 'a' * 20}]
    await bootstrap.fetch_bootstrap_peers()

    # Assuming DHT returns two peers for bootstrap download
    assert bootstrap.bootstrap_nodes['a' * 20]
    assert bootstrap.bootstrap_nodes['b' * 20]
