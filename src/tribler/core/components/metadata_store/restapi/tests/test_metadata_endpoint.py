from unittest.mock import MagicMock

import pytest

from tribler.core.components.metadata_store.restapi.metadata_endpoint import MetadataEndpoint, TORRENT_CHECK_TIMEOUT
from tribler.core.components.restapi.rest.base_api_test import do_request
from tribler.core.components.torrent_checker.torrent_checker.torrent_checker import TorrentChecker
from tribler.core.config.tribler_config import TriblerConfig
from tribler.core.utilities.unicode import hexlify


# pylint: disable=unused-argument, redefined-outer-name

@pytest.fixture
async def torrent_checker(mock_dlmgr, metadata_store):
    # Initialize the torrent checker
    config = TriblerConfig()
    config.download_defaults.number_hops = 0
    tracker_manager = MagicMock()
    tracker_manager.blacklist = []
    notifier = MagicMock()
    torrent_checker = TorrentChecker(
        config=config,
        download_manager=mock_dlmgr,
        tracker_manager=tracker_manager,
        metadata_store=metadata_store,
        notifier=notifier,
        socks_listen_ports=[2000, 3000],
    )
    await torrent_checker.initialize()
    yield torrent_checker
    await torrent_checker.shutdown()


@pytest.fixture
def endpoint(torrent_checker, metadata_store):
    return MetadataEndpoint(torrent_checker.download_manager, torrent_checker, metadata_store)


async def test_check_torrent_health(rest_api, mock_dlmgr, udp_tracker, metadata_store):
    """
    Test the endpoint to fetch the health of a chant-managed, infohash-only torrent
    """
    infohash = b'a' * 20
    url = f'metadata/torrents/{hexlify(infohash)}/health?timeout={TORRENT_CHECK_TIMEOUT}'
    json_response = await do_request(rest_api, url)
    assert json_response == {'checking': True}


async def test_check_torrent_query(rest_api, udp_tracker, metadata_store):
    """
    Test that the endpoint responds with an error message if the timeout parameter has a wrong value
    """
    infohash = b'a' * 20
    await do_request(rest_api, f"metadata/torrents/{infohash}/health?timeout=wrong_value&refresh=1", expected_code=400)
