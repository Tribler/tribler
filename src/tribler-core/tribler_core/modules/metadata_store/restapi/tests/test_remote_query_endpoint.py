import uuid
from unittest.mock import Mock

import pytest

from tribler_core.restapi.base_api_test import do_request


@pytest.mark.asyncio
async def test_create_remote_search_request(enable_chant, enable_api, session):
    """
    Test that remote search call is sent on a REST API search request
    """
    sent = {}
    request_uuid = uuid.uuid4()

    def mock_send(**kwargs):
        sent.update(kwargs)
        return request_uuid

    # Test querying for keywords
    session.gigachannel_community = Mock()
    session.gigachannel_community.send_search_request = mock_send
    search_txt = "foo"
    await do_request(
        session,
        f'remote_query?txt_filter={search_txt}',
        request_type="PUT",
        expected_code=200,
        expected_json={"request_uuid": str(request_uuid)},
    )
    assert sent['txt_filter'] == search_txt
    sent.clear()

    # Test querying channel data by public key, e.g. for channel preview purposes
    channel_pk = "ff"
    await do_request(
        session, f'remote_query?channel_pk={channel_pk}&metadata_type=torrent', request_type="PUT", expected_code=200
    )
    assert sent['channel_pk'] == channel_pk
