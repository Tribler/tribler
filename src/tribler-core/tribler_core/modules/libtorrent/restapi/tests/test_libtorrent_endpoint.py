from unittest.mock import Mock

import pytest

from tribler_core.restapi.base_api_test import do_request
from tribler_core.utilities.unicode import hexlify


@pytest.fixture
def mock_lt_session(mock_dlmgr, session):
    mock_alert = Mock()
    mock_alert.values = {"a": "b"}

    lt_session = Mock()
    lt_session.post_session_stats = lambda: session.dlmgr.session_stats_callback(mock_alert)
    lt_session.settings = {"peer_fingerprint": b"abcd", "user_agent": "Tribler"}

    anon_lt_session = Mock()
    anon_lt_session.get_settings = lambda: {"user_agent": "libtorrent"}

    session.dlmgr.ltsessions = {0: lt_session, 1: anon_lt_session}
    session.dlmgr.get_session_settings = lambda ses: ses.settings
    return lt_session


@pytest.mark.asyncio
async def test_get_settings_zero_hop(enable_api, mock_lt_session, session):
    """
    Tests getting session settings for zero hop session.
    By default, there should always be a zero hop session so we should be able to get settings for
    zero hop session.
    """
    hop = 0
    response_dict = await do_request(session, 'libtorrent/settings?hop=%d' % hop, expected_code=200)
    settings_dict = response_dict['settings']
    assert response_dict['hop'] == hop
    assert hexlify(b"abcd") == settings_dict["peer_fingerprint"]
    assert "Tribler" in settings_dict['user_agent']


@pytest.mark.asyncio
async def test_get_settings_for_uninitialized_session(enable_api, mock_dlmgr, session):
    """
    Tests getting session for non initialized session.
    By default, anonymous sessions with hops > 1 are not initialized so test is done for
    a 2 hop session expecting empty stats.
    """
    hop = 2
    response_dict = await do_request(session, 'libtorrent/settings?hop=%d' % hop, expected_code=200)
    assert response_dict['hop'] == hop
    assert response_dict['settings'] == {}


@pytest.mark.asyncio
async def test_get_settings_for_one_session(enable_api, mock_lt_session, session):
    """
    Tests getting session for initialized anonymous session.
    """
    hop = 1
    response_dict = await do_request(session, 'libtorrent/settings?hop=%d' % hop, expected_code=200)
    settings_dict = response_dict['settings']
    assert response_dict['hop'] == hop
    assert "libtorrent" in settings_dict['user_agent'] or settings_dict['user_agent'] == ''


@pytest.mark.asyncio
async def test_get_stats_zero_hop_session(enable_api, mock_lt_session, session):
    """
    Tests getting session stats for zero hop session.
    By default, there should always be a zero hop session so we should be able to get stats for this session.
    """
    hop = 0
    response_dict = await do_request(session, 'libtorrent/session?hop=%d' % hop, expected_code=200)
    assert response_dict['hop'] == hop
    assert response_dict["session"] == {"a": "b"}


@pytest.mark.asyncio
async def test_get_stats_for_uninitialized_session(enable_api, mock_dlmgr, session):
    """
    Tests getting stats for non initialized session.
    By default, anonymous sessions with hops > 1 are not initialized so test is done for
    a 2 hop session expecting empty stats.
    """
    hop = 2

    response_dict = await do_request(session, 'libtorrent/session?hop=%d' % hop, expected_code=200)
    assert response_dict['hop'] == hop
    assert response_dict['session'] == {}
