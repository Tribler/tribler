import pytest
from ipv8.keyvault.crypto import default_eccrypto
from ipv8.peer import Peer

from tribler.core.components.bandwidth_accounting.community.bandwidth_accounting_community import (
    BandwidthAccountingCommunity,
)
from tribler.core.components.bandwidth_accounting.db.database import BandwidthDatabase
from tribler.core.components.bandwidth_accounting.db.transaction import BandwidthTransactionData, EMPTY_SIGNATURE
from tribler.core.components.bandwidth_accounting.restapi.bandwidth_endpoint import BandwidthEndpoint
from tribler.core.components.bandwidth_accounting.settings import BandwidthAccountingSettings
from tribler.core.components.ipv8.adapters_tests import TriblerMockIPv8
from tribler.core.components.restapi.rest.base_api_test import do_request
from tribler.core.utilities.unicode import hexlify


# pylint: disable=redefined-outer-name
@pytest.fixture
def peer():
    return Peer(default_eccrypto.generate_key("curve25519"), address=("1.2.3.4", 5))


@pytest.fixture
def bandwidth_database(tmp_path, peer):
    return BandwidthDatabase(db_path=tmp_path / "bandwidth.db", my_pub_key=peer.public_key.key_to_bin())


@pytest.fixture
async def bw_community(bandwidth_database, peer):
    ipv8 = TriblerMockIPv8(peer, BandwidthAccountingCommunity,
                           database=bandwidth_database,
                           settings=BandwidthAccountingSettings())
    community = ipv8.get_overlay(BandwidthAccountingCommunity)
    yield community
    await ipv8.stop()


@pytest.fixture
async def bw_endpoint(bw_community):
    endpoint = BandwidthEndpoint(bw_community)
    endpoint.setup_routes()
    return endpoint


async def test_get_statistics(bw_endpoint, bw_community, aiohttp_client):
    """
    Testing whether the API returns the correct statistics
    """
    bw_endpoint.bandwidth_community = bw_community
    my_pk = bw_community.database.my_pub_key
    tx1 = BandwidthTransactionData(1, b"a", my_pk, EMPTY_SIGNATURE, EMPTY_SIGNATURE, 3000)
    tx2 = BandwidthTransactionData(1, my_pk, b"a", EMPTY_SIGNATURE, EMPTY_SIGNATURE, 2000)
    bw_community.database.BandwidthTransaction.insert(tx1)
    bw_community.database.BandwidthTransaction.insert(tx2)

    response_dict = await do_request(await aiohttp_client(bw_endpoint.app), 'statistics', expected_code=200)
    assert "statistics" in response_dict
    stats = response_dict["statistics"]
    assert stats["id"] == hexlify(my_pk)
    assert stats["total_given"] == 3000
    assert stats["total_taken"] == 2000
    assert stats["num_peers_helped"] == 1
    assert stats["num_peers_helped_by"] == 1


async def test_get_history(bw_endpoint, bw_community, aiohttp_client):
    """
    Testing whether the API returns the correct bandwidth balance history
    """
    bw_endpoint.bandwidth_community = bw_community
    my_pk = bw_community.my_peer.public_key.key_to_bin()
    tx1 = BandwidthTransactionData(1, b"a", my_pk, EMPTY_SIGNATURE, EMPTY_SIGNATURE, 3000)
    tx2 = BandwidthTransactionData(1, my_pk, b"a", EMPTY_SIGNATURE, EMPTY_SIGNATURE, 2000)
    bw_community.database.BandwidthTransaction.insert(tx1)
    bw_community.database.BandwidthTransaction.insert(tx2)

    response_dict = await do_request(await aiohttp_client(bw_endpoint.app), 'history', expected_code=200)
    assert "history" in response_dict
    assert len(response_dict["history"]) == 2
