from ipv8.test.mocking.ipv8 import MockIPv8

import pytest

from tribler_core.modules.bandwidth_accounting import EMPTY_SIGNATURE
from tribler_core.modules.bandwidth_accounting.community import BandwidthAccountingCommunity
from tribler_core.modules.bandwidth_accounting.transaction import BandwidthTransactionData
from tribler_core.restapi.base_api_test import do_request
from tribler_core.utilities.unicode import hexlify


@pytest.fixture
async def mock_ipv8(session):
    db_path = session.config.get_state_dir() / "bandwidth.db"
    mock_ipv8 = MockIPv8("low", BandwidthAccountingCommunity, database_path=db_path)
    session.bandwidth_community = mock_ipv8.overlay
    yield mock_ipv8
    await mock_ipv8.stop()


@pytest.mark.asyncio
async def test_get_statistics_no_community(enable_api, session):
    """
    Testing whether the API returns error 404 if no bandwidth community is loaded
    """
    await do_request(session, 'bandwidth/statistics', expected_code=404)


@pytest.mark.asyncio
async def test_get_statistics(enable_api, mock_ipv8, session):
    """
    Testing whether the API returns the correct statistics
    """
    my_pk = session.bandwidth_community.my_peer.public_key.key_to_bin()
    tx1 = BandwidthTransactionData(1, b"a", my_pk, EMPTY_SIGNATURE, EMPTY_SIGNATURE, 3000)
    tx2 = BandwidthTransactionData(1, my_pk, b"a", EMPTY_SIGNATURE, EMPTY_SIGNATURE, 2000)
    session.bandwidth_community.database.BandwidthTransaction.insert(tx1)
    session.bandwidth_community.database.BandwidthTransaction.insert(tx2)

    response_dict = await do_request(session, 'bandwidth/statistics', expected_code=200)
    assert "statistics" in response_dict
    stats = response_dict["statistics"]
    assert stats["id"] == hexlify(my_pk)
    assert stats["total_given"] == 3000
    assert stats["total_taken"] == 2000
    assert stats["num_peers_helped"] == 1
    assert stats["num_peers_helped_by"] == 1


@pytest.mark.asyncio
async def test_get_history_no_community(enable_api, session):
    """
    Testing whether the API returns error 404 if no bandwidth community is loaded
    """
    await do_request(session, 'bandwidth/history', expected_code=404)


@pytest.mark.asyncio
async def test_get_history(enable_api, mock_ipv8, session):
    """
    Testing whether the API returns the correct bandwidth balance history
    """
    my_pk = session.bandwidth_community.my_peer.public_key.key_to_bin()
    tx1 = BandwidthTransactionData(1, b"a", my_pk, EMPTY_SIGNATURE, EMPTY_SIGNATURE, 3000)
    tx2 = BandwidthTransactionData(1, my_pk, b"a", EMPTY_SIGNATURE, EMPTY_SIGNATURE, 2000)
    session.bandwidth_community.database.BandwidthTransaction.insert(tx1)
    session.bandwidth_community.database.BandwidthTransaction.insert(tx2)

    response_dict = await do_request(session, 'bandwidth/history', expected_code=200)
    assert "history" in response_dict
    assert len(response_dict["history"]) == 2
