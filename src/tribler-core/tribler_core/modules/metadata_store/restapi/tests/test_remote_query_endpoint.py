from unittest.mock import Mock

import pytest

from tribler_core.restapi.base_api_test import do_request


@pytest.mark.asyncio
async def test_create_remote_search_request(enable_chant, enable_api, session):
    """
    Test that remote search call is sent on a REST API search request
    """
    sent = []

    def mock_send(txt_filter, **__):
        sent.append(txt_filter)

    session.gigachannel_community = Mock()
    session.gigachannel_community.send_search_request = mock_send
    search_txt = "foo"
    await do_request(session, f'remote_query?txt_filter={search_txt}&uuid=333', request_type="PUT", expected_code=200)
    assert search_txt in sent

    # Test querying channel data by public key, e.g. for channel preview purposes
    channel_pk = "ff"
    await do_request(session, f'remote_query?channel_pk={channel_pk}&uuid=333', request_type="PUT", expected_code=200)
    assert f'"{channel_pk}"*' in sent

    await do_request(
        session,
        f'remote_query?txt_filter={search_txt}&channel_pk={channel_pk}&uuid=333',
        request_type="PUT",
        expected_code=400,
    )
