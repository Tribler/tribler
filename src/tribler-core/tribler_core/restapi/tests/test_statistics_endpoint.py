from pathlib import Path

from ipv8.test.mocking.ipv8 import MockIPv8

import pytest

from tribler_core.modules.bandwidth_accounting.community import BandwidthAccountingCommunity
from tribler_core.restapi.base_api_test import do_request


@pytest.fixture
async def mock_ipv8(session):
    db_path = Path(":memory:")
    mock_ipv8 = MockIPv8("low", BandwidthAccountingCommunity, database_path=db_path)
    mock_ipv8.overlays = [mock_ipv8.overlay]
    mock_ipv8.endpoint.bytes_up = 100
    mock_ipv8.endpoint.bytes_down = 20
    session.ipv8 = mock_ipv8
    session.config.set_ipv8_enabled(True)
    yield mock_ipv8
    session.ipv8 = None
    await mock_ipv8.stop()


@pytest.mark.asyncio
async def test_get_tribler_statistics(enable_chant, enable_api, session):
    """
    Testing whether the API returns a correct Tribler statistics dictionary when requested
    """
    json_data = await do_request(session, 'statistics/tribler', expected_code=200)
    assert "tribler_statistics" in json_data


@pytest.mark.asyncio
async def test_get_ipv8_statistics(enable_api, mock_ipv8, session):
    """
    Testing whether the API returns a correct IPv8 statistics dictionary when requested
    """
    json_data = await do_request(session, 'statistics/ipv8', expected_code=200)
    assert json_data["ipv8_statistics"]


@pytest.mark.asyncio
async def test_get_ipv8_statistics_unavailable(enable_api, session):
    """
    Testing whether the API returns error 500 if IPv8 is not available
    """
    json_data = await do_request(session, 'statistics/ipv8', expected_code=200)
    assert not json_data["ipv8_statistics"]
