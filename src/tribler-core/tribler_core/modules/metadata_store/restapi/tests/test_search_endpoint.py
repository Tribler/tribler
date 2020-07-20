from ipv8.database import database_blob

from pony.orm import db_session

import pytest

from tribler_core.restapi.base_api_test import do_request
from tribler_core.utilities.random_utils import random_infohash


@pytest.mark.asyncio
async def test_search_no_query(enable_chant, enable_api, session):
    """
    Testing whether the API returns an error 400 if no query is passed when doing a search
    """
    await do_request(session, 'search', expected_code=400)


@pytest.mark.asyncio
async def test_search_wrong_mdtype(enable_chant, enable_api, session):
    """
    Testing whether the API returns an error 400 if wrong metadata type is passed in the query
    """
    await do_request(session, 'search?txt_filter=bla&metadata_type=ddd', expected_code=400)


@pytest.mark.asyncio
async def test_search(enable_chant, enable_api, session):
    """
    Test a search query that should return a few new type channels
    """
    num_hay = 100
    with db_session:
        _ = session.mds.ChannelMetadata(title='test', tags='test', subscribed=True, infohash=random_infohash())
        for x in range(0, num_hay):
            session.mds.TorrentMetadata(title='hay ' + str(x), infohash=random_infohash())
        session.mds.TorrentMetadata(title='needle', infohash=database_blob(bytearray(random_infohash())))
        session.mds.TorrentMetadata(title='needle2', infohash=database_blob(bytearray(random_infohash())))

    parsed = await do_request(session, 'search?txt_filter=needle', expected_code=200)
    assert len(parsed["results"]) == 1

    parsed = await do_request(session, 'search?txt_filter=hay', expected_code=200)
    assert len(parsed["results"]) == 50

    parsed = await do_request(session, 'search?txt_filter=test&type=channel', expected_code=200)
    assert len(parsed["results"]) == 1

    parsed = await do_request(session, 'search?txt_filter=needle&type=torrent', expected_code=200)
    assert parsed["results"][0]['name'] == 'needle'

    parsed = await do_request(session, 'search?txt_filter=needle&sort_by=name', expected_code=200)
    assert len(parsed["results"]) == 1

    parsed = await do_request(session, 'search?txt_filter=needle%2A&sort_by=name&sort_desc=1', expected_code=200)
    assert len(parsed["results"]) == 2
    assert parsed["results"][0]['name'] == "needle2"

    # Test getting total count of results
    parsed = await do_request(session, 'search?txt_filter=needle&include_total=1', expected_code=200)
    assert parsed["total"] == 1

    # Test getting total count of results
    parsed = await do_request(session, 'search?txt_filter=hay&include_total=1', expected_code=200)
    assert parsed["total"] == 100


@pytest.mark.asyncio
async def test_completions_no_query(enable_chant, enable_api, session):
    """
    Testing whether the API returns an error 400 if no query is passed when getting search completion terms
    """
    await do_request(session, 'search/completions', expected_code=400)


@pytest.mark.asyncio
async def test_completions(enable_chant, enable_api, session):
    """
    Testing whether the API returns the right terms when getting search completion terms
    """
    json_response = await do_request(session, 'search/completions?q=tribler', expected_code=200)
    assert json_response['completions'] == []
