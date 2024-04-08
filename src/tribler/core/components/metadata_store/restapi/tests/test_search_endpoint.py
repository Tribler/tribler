import os
from typing import Set
from unittest.mock import patch

import pytest
from pony.orm import db_session

from tribler.core.components.knowledge.db.knowledge_db import KnowledgeDatabase
from tribler.core.components.metadata_store.restapi.search_endpoint import SearchEndpoint
from tribler.core.components.restapi.rest.base_api_test import do_request
from tribler.core.utilities.unicode import hexlify
from tribler.core.utilities.utilities import random_infohash, to_fts_query


# pylint: disable=unused-argument, redefined-outer-name


@pytest.fixture
def needle_in_haystack_mds(metadata_store):
    num_hay = 100
    with db_session:
        _ = metadata_store.ChannelMetadata(title='test', tags='test', subscribed=True, infohash=random_infohash())
        for x in range(0, num_hay):
            metadata_store.TorrentMetadata(title='hay ' + str(x), infohash=random_infohash())
        metadata_store.TorrentMetadata(title='needle', infohash=random_infohash())
        metadata_store.TorrentMetadata(title='needle2', infohash=random_infohash())
    return metadata_store


@pytest.fixture
def rest_api(web_app, event_loop, needle_in_haystack_mds, aiohttp_client, knowledge_db):
    channels_endpoint = SearchEndpoint(needle_in_haystack_mds, knowledge_db=knowledge_db)
    web_app.add_subapp('/search', channels_endpoint.app)
    yield event_loop.run_until_complete(aiohttp_client(web_app))


async def test_search_wrong_mdtype(rest_api):
    """
    Testing whether the API returns an error 400 if wrong metadata type is passed in the query
    """
    await do_request(rest_api, 'search?txt_filter=bla&metadata_type=ddd', expected_code=400)


async def test_search(rest_api):
    """
    Test a search query that should return a few new type channels
    """

    parsed = await do_request(rest_api, 'search?txt_filter=needle', expected_code=200)
    assert len(parsed["results"]) == 1

    parsed = await do_request(rest_api, 'search?txt_filter=hay', expected_code=200)
    assert len(parsed["results"]) == 50

    parsed = await do_request(rest_api, 'search?txt_filter=test&type=channel', expected_code=200)
    assert len(parsed["results"]) == 1

    parsed = await do_request(rest_api, 'search?txt_filter=needle&type=torrent', expected_code=200)
    assert parsed["results"][0]['name'] == 'needle'

    parsed = await do_request(rest_api, 'search?txt_filter=needle&sort_by=name', expected_code=200)
    assert len(parsed["results"]) == 1

    parsed = await do_request(rest_api, 'search?txt_filter=needle%2A&sort_by=name&sort_desc=1', expected_code=200)
    assert len(parsed["results"]) == 2
    assert parsed["results"][0]['name'] == "needle2"


async def test_search_by_tags(rest_api):
    def mocked_get_subjects_intersection(*_, objects: Set[str], **__):
        if objects.pop() == 'missed_tag':
            return None
        return {hexlify(os.urandom(20))}

    with patch.object(KnowledgeDatabase, 'get_subjects_intersection', wraps=mocked_get_subjects_intersection):
        parsed = await do_request(rest_api, 'search?txt_filter=needle&tags=real_tag', expected_code=200)
        assert len(parsed["results"]) == 0

        parsed = await do_request(rest_api, 'search?txt_filter=needle&tags=missed_tag', expected_code=200)
        assert len(parsed["results"]) == 1


async def test_search_with_include_total_and_max_rowid(rest_api):
    """
    Test search queries with include_total and max_rowid options
    """

    parsed = await do_request(rest_api, 'search?txt_filter=needle', expected_code=200)
    assert len(parsed["results"]) == 1
    assert "total" not in parsed
    assert "max_rowid" not in parsed

    parsed = await do_request(rest_api, 'search?txt_filter=needle&include_total=1', expected_code=200)
    assert parsed["total"] == 1
    assert parsed["max_rowid"] == 103

    parsed = await do_request(rest_api, 'search?txt_filter=hay&include_total=1', expected_code=200)
    assert parsed["total"] == 100
    assert parsed["max_rowid"] == 103

    parsed = await do_request(rest_api, 'search?txt_filter=hay', expected_code=200)
    assert len(parsed["results"]) == 50

    parsed = await do_request(rest_api, 'search?txt_filter=hay&max_rowid=0', expected_code=200)
    assert len(parsed["results"]) == 0

    parsed = await do_request(rest_api, 'search?txt_filter=hay&max_rowid=20', expected_code=200)
    assert len(parsed["results"]) == 19

    parsed = await do_request(rest_api, 'search?txt_filter=needle&sort_by=name', expected_code=200)
    assert len(parsed["results"]) == 1

    parsed = await do_request(rest_api, 'search?txt_filter=needle&sort_by=name&max_rowid=20', expected_code=200)
    assert len(parsed["results"]) == 0

    parsed = await do_request(rest_api, 'search?txt_filter=needle&sort_by=name&max_rowid=200', expected_code=200)
    assert len(parsed["results"]) == 1


async def test_completions_no_query(rest_api):
    """
    Testing whether the API returns an error 400 if no query is passed when getting search completion terms
    """
    await do_request(rest_api, 'search/completions', expected_code=400)


async def test_completions(rest_api):
    """
    Testing whether the API returns the right terms when getting search completion terms
    """
    json_response = await do_request(rest_api, 'search/completions?q=tribler', expected_code=200)
    assert json_response['completions'] == []


async def test_search_with_space(rest_api, metadata_store):
    with db_session:
        _ = metadata_store.ChannelMetadata(title='test', tags='test', subscribed=True, infohash=random_infohash())
        metadata_store.TorrentMetadata(title='abc', infohash=random_infohash())
        metadata_store.TorrentMetadata(title='abc.def', infohash=random_infohash())
        metadata_store.TorrentMetadata(title='abc def', infohash=random_infohash())
        metadata_store.TorrentMetadata(title='abcxyz def', infohash=random_infohash())
        metadata_store.TorrentMetadata(title='abc defxyz', infohash=random_infohash())

    s1 = to_fts_query("abc")
    assert s1 == '"abc"'

    s2 = to_fts_query("abc def")
    assert s2 == '"abc" "def"'

    ss2 = to_fts_query(s2)
    assert ss2 == s2

    parsed = await do_request(rest_api, f'search?txt_filter={s1}', expected_code=200)
    results = {item["name"] for item in parsed["results"]}
    assert results == {'abc', 'abc.def', 'abc def', 'abc defxyz'}

    parsed = await do_request(rest_api, f'search?txt_filter={s2}', expected_code=200)
    results = {item["name"] for item in parsed["results"]}
    assert results == {'abc.def', 'abc def'}  # but not 'abcxyz def'
