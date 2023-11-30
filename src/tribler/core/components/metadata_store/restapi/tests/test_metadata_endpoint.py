from unittest.mock import MagicMock, Mock, AsyncMock

import pytest

from tribler.core.components.metadata_store.db.serialization import REGULAR_TORRENT
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


async def test_get_popular_torrents(rest_api, endpoint, metadata_store):
    """
    Test that the endpoint responds with its known entries.
    """
    fake_entry = {
                "name": "Torrent Name",
                "category": "",
                "infohash": "ab" * 20,
                "size": 1,
                "num_seeders": 1234,
                "num_leechers": 123,
                "last_tracker_check": 17000000,
                "created": 15000000,
                "tag_processor_version": 1,
                "type": REGULAR_TORRENT,
                "id": 0,
                "origin_id": 0,
                "public_key": "ab" * 64,
                "status": 2,
            }
    fake_state = Mock(return_value=Mock(get_progress=Mock(return_value=0.5)))
    metadata_store.get_entries = Mock(return_value=[Mock(to_simple_dict=Mock(return_value=fake_entry.copy()))])
    endpoint.tag_rules_processor = Mock(process_queue=AsyncMock())
    endpoint.download_manager.get_download = Mock(return_value=Mock(get_state=fake_state))
    response = await do_request(rest_api, f"metadata/torrents/popular")

    endpoint.tag_rules_processor.process_queue.assert_called_once()
    assert response == {'results': [{**fake_entry, **{"progress": 0.5}}], 'first': 1, 'last': 50}
