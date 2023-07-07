from unittest.mock import Mock

import pytest

from tribler.core.components.libtorrent.restapi.libtorrent_endpoint import LibTorrentEndpoint
from tribler.core.components.restapi.rest.base_api_test import do_request
from tribler.core.utilities.unicode import hexlify


# pylint: disable=redefined-outer-name

@pytest.fixture
def endpoint(mock_dlmgr, mock_lt_session):
    return LibTorrentEndpoint(mock_dlmgr)


@pytest.fixture
def mock_lt_session(mock_dlmgr):
    mock_alert = Mock()
    mock_alert.values = {"a": "b"}

    lt_session = Mock()
    lt_session.post_session_stats = lambda: mock_dlmgr.session_stats_callback(mock_alert)
    lt_session.settings = {"peer_fingerprint": b"abcd", "user_agent": "Tribler"}

    anon_lt_session = Mock()
    anon_lt_session.get_settings = lambda: {"user_agent": "libtorrent"}

    mock_dlmgr.ltsessions = {0: lt_session, 1: anon_lt_session}
    mock_dlmgr.get_session_settings = lambda ses: ses.settings
    return lt_session


async def test_get_settings_zero_hop(rest_api):
    """
    Tests getting rest_api settings for zero hop rest_api.
    By default, there should always be a zero hop rest_api so we should be able to get settings for
    zero hop rest_api.
    """
    hop = 0
    response_dict = await do_request(rest_api, 'libtorrent/settings?hop=%d' % hop, expected_code=200)
    settings_dict = response_dict['settings']
    assert response_dict['hop'] == hop
    assert hexlify(b"abcd") == settings_dict["peer_fingerprint"]
    assert "Tribler" in settings_dict['user_agent']


async def test_get_settings_for_uninitialized_session(rest_api):
    """
    Tests getting rest_api for non initialized rest_api.
    By default, anonymous sessions with hops > 1 are not initialized so test is done for
    a 2 hop rest_api expecting empty stats.
    """
    hop = 2
    response_dict = await do_request(rest_api, 'libtorrent/settings?hop=%d' % hop, expected_code=200)
    assert response_dict['hop'] == hop
    assert response_dict['settings'] == {}


async def test_get_settings_for_one_session(rest_api):
    """
    Tests getting rest_api for initialized anonymous rest_api.
    """
    hop = 1
    response_dict = await do_request(rest_api, 'libtorrent/settings?hop=%d' % hop, expected_code=200)
    settings_dict = response_dict['settings']
    assert response_dict['hop'] == hop
    assert "libtorrent" in settings_dict['user_agent'] or settings_dict['user_agent'] == ''


async def test_get_stats_zero_hop_session(rest_api):
    """
    Tests getting rest_api stats for zero hop rest_api.
    By default, there should always be a zero hop rest_api so we should be able to get stats for this rest_api.
    """
    hop = 0
    response_dict = await do_request(rest_api, 'libtorrent/session?hop=%d' % hop, expected_code=200)
    assert response_dict['hop'] == hop
    assert response_dict["session"] == {"a": "b"}


async def test_get_stats_for_uninitialized_session(rest_api):
    """
    Tests getting stats for non initialized rest_api.
    By default, anonymous sessions with hops > 1 are not initialized so test is done for
    a 2 hop rest_api expecting empty stats.
    """
    hop = 2

    response_dict = await do_request(rest_api, 'libtorrent/session?hop=%d' % hop, expected_code=200)
    assert response_dict['hop'] == hop
    assert response_dict['session'] == {}
