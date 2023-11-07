import os
from binascii import unhexlify
from typing import List, Set
from unittest.mock import patch

import pytest
from pony.orm import db_session

from tribler.core.components.database.db.layers.knowledge_data_access_layer import KnowledgeDataAccessLayer
from tribler.core.components.metadata_store.db.serialization import REGULAR_TORRENT, SNIPPET
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
def endpoint(needle_in_haystack_mds, tribler_db):
    return SearchEndpoint(needle_in_haystack_mds, tribler_db=tribler_db)


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

    with patch.object(KnowledgeDataAccessLayer, 'get_subjects_intersection', wraps=mocked_get_subjects_intersection):
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


async def test_single_snippet_in_search(rest_api, metadata_store, tribler_db):
    """
    Test building a simple snippet of a single item.
    """
    with db_session:
        content_ih = random_infohash()
        metadata_store.TorrentMetadata(title='abc', infohash=content_ih)

    def mocked_get_subjects(*_, **__) -> List[str]:
        return ["Abc"]

    with patch.object(KnowledgeDataAccessLayer, 'get_objects', wraps=mocked_get_subjects):
        s1 = to_fts_query("abc")
        results = await do_request(rest_api, f'search?txt_filter={s1}', expected_code=200)

        assert len(results["results"]) == 1
        snippet = results["results"][0]
        assert snippet["type"] == SNIPPET
        assert snippet["torrents"] == 1
        assert len(snippet["torrents_in_snippet"]) == 1
        assert snippet["torrents_in_snippet"][0]["infohash"] == hexlify(content_ih)


async def test_multiple_snippets_in_search(rest_api, metadata_store, tribler_db):
    """
    Test two snippets with two torrents in each snippet.
    """
    with db_session:
        infohashes = [random_infohash() for _ in range(5)]
        for ind, infohash in enumerate(infohashes):
            torrent_state = metadata_store.TorrentState(infohash=infohash, seeders=ind)
            metadata_store.TorrentMetadata(title=f'abc {ind}', infohash=infohash, health=torrent_state)

    def mocked_get_objects(*__, subject=None, **___) -> List[str]:
        subject = unhexlify(subject)
        if subject in {infohashes[0], infohashes[1]}:
            return ["Content item 1"]
        if subject in {infohashes[2], infohashes[3]}:
            return ["Content item 2"]
        return []

    with patch.object(KnowledgeDataAccessLayer, 'get_objects', wraps=mocked_get_objects):
        s1 = to_fts_query("abc")
        parsed = await do_request(rest_api, f'search?txt_filter={s1}', expected_code=200)
        results = parsed["results"]

        assert len(results) == 3
        for snippet in results[:2]:
            assert snippet["type"] == SNIPPET
            assert snippet["torrents"] == 2

        # Test that the right torrents have been assigned to the appropriate content items, and that they are in the
        # right sorted order.
        assert results[0]["torrents_in_snippet"][0]["infohash"] == hexlify(infohashes[3])
        assert results[0]["torrents_in_snippet"][1]["infohash"] == hexlify(infohashes[2])
        assert results[1]["torrents_in_snippet"][0]["infohash"] == hexlify(infohashes[1])
        assert results[1]["torrents_in_snippet"][1]["infohash"] == hexlify(infohashes[0])

        # There is one item that has not been assigned to the snippet.
        assert results[2]["type"] == REGULAR_TORRENT
        assert results[2]["infohash"] == hexlify(infohashes[4])


def test_build_snippets_no_infohash(endpoint: SearchEndpoint):
    """ Test building snippets without infohash. The `build_snippets` should return the same results."""
    search_results = [{'dictionary': 'without infohash'}]
    result = endpoint.build_snippets(search_results)
    assert result == search_results
