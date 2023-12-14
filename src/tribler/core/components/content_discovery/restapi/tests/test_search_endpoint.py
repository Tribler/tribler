import uuid
from unittest.mock import Mock

import pytest

from tribler.core.components.content_discovery.restapi.search_endpoint import SearchEndpoint
from tribler.core.components.restapi.rest.base_api_test import do_request
from tribler.core.utilities.unicode import hexlify


@pytest.fixture(name="mock_content_discovery_community")
def fixture_mock_content_discovery_community():
    return Mock()


@pytest.fixture(name="endpoint")
def fixture_endpoint(mock_content_discovery_community):
    return SearchEndpoint(mock_content_discovery_community)


async def test_create_remote_search_request(rest_api, mock_content_discovery_community):
    """
    Test that remote search call is sent on a REST API search request
    """
    sent = {}
    peers = []
    request_uuid = uuid.uuid4()

    def mock_send(**kwargs):
        sent.update(kwargs)
        return request_uuid, peers

    # Test querying for keywords
    mock_content_discovery_community.send_search_request = mock_send
    search_txt = "foo"
    await do_request(
        rest_api,
        f'search/remote?txt_filter={search_txt}&max_rowid=1',
        request_type="PUT",
        expected_code=200,
        expected_json={"request_uuid": str(request_uuid), "peers": peers},
    )
    assert sent['txt_filter'] == search_txt
    sent.clear()

    # Test querying channel data by public key, e.g. for channel preview purposes
    channel_pk = "ff"
    await do_request(
        rest_api, f'search/remote?channel_pk={channel_pk}&metadata_type=torrent', request_type="PUT", expected_code=200
    )
    assert hexlify(sent['channel_pk']) == channel_pk


async def test_create_remote_search_request_illegal(rest_api):
    """
    Test that remote search call is sent on a REST API search request
    """
    response = await do_request(
        rest_api,
        'search/remote?origin_id=a',
        request_type="PUT",
        expected_code=400
    )
    assert "error" in response
