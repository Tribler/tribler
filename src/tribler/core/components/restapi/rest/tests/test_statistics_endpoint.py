from unittest.mock import MagicMock, Mock

import pytest

from tribler.core.components.ipv8.adapters_tests import TriblerMockIPv8
from tribler.core.components.restapi.rest.base_api_test import do_request
from tribler.core.components.restapi.rest.statistics_endpoint import StatisticsEndpoint
from tribler.core.components.tunnel.community.tunnel_community import TriblerTunnelCommunity
from tribler.core.components.tunnel.settings import TunnelCommunitySettings


# pylint: disable=redefined-outer-name


@pytest.fixture
async def endpoint(metadata_store):
    ipv8 = TriblerMockIPv8("curve25519",
                           TriblerTunnelCommunity,
                           settings={"max_circuits": 1},
                           config=TunnelCommunitySettings(),
                           socks_servers=MagicMock(),
                           dlmgr=Mock())
    ipv8.overlays = [ipv8.overlay]
    ipv8.endpoint.bytes_up = 100
    ipv8.endpoint.bytes_down = 20

    endpoint = StatisticsEndpoint(ipv8, metadata_store)

    yield endpoint

    await ipv8.stop()


async def test_get_tribler_statistics(rest_api):
    """
    Testing whether the API returns a correct Tribler statistics dictionary when requested
    """
    stats = (await do_request(rest_api, 'statistics/tribler', expected_code=200))['tribler_statistics']
    assert 'db_size' in stats
    assert 'num_torrents' in stats


async def test_get_ipv8_statistics(rest_api):
    """
    Testing whether the API returns a correct IPv8 statistics dictionary when requested
    """
    json_data = await do_request(rest_api, 'statistics/ipv8', expected_code=200)
    assert json_data["ipv8_statistics"]


async def test_get_ipv8_statistics_unavailable(rest_api, endpoint: StatisticsEndpoint):
    """
    Testing whether the API returns error 500 if IPv8 is not available
    """
    endpoint.ipv8 = None
    json_data = await do_request(rest_api, 'statistics/ipv8', expected_code=200)
    assert not json_data["ipv8_statistics"]
