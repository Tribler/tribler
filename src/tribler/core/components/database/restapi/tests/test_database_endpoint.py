import os
from binascii import unhexlify
from typing import List, Set
from unittest.mock import MagicMock, Mock, AsyncMock, patch

import pytest
from pony.orm import db_session

from tribler.core.components.database.category_filter.family_filter import default_xxx_filter
from tribler.core.components.database.db.layers.knowledge_data_access_layer import KnowledgeDataAccessLayer
from tribler.core.components.database.db.serialization import REGULAR_TORRENT, SNIPPET
from tribler.core.components.database.restapi.database_endpoint import DatabaseEndpoint, TORRENT_CHECK_TIMEOUT
from tribler.core.components.restapi.rest.base_api_test import do_request
from tribler.core.components.torrent_checker.torrent_checker.torrent_checker import TorrentChecker
from tribler.core.config.tribler_config import TriblerConfig
from tribler.core.utilities.unicode import hexlify
from tribler.core.utilities.utilities import random_infohash, to_fts_query


@pytest.fixture(name="needle_in_haystack_mds")
def fixture_needle_in_haystack_mds(metadata_store):
    num_hay = 100
    with db_session:
        for x in range(0, num_hay):
            metadata_store.TorrentMetadata(title='hay ' + str(x), infohash=random_infohash(), public_key=b'')
        metadata_store.TorrentMetadata(title='needle', infohash=random_infohash(), public_key=b'')
        metadata_store.TorrentMetadata(title='needle2', infohash=random_infohash(), public_key=b'')
    return metadata_store


@pytest.fixture(name="torrent_checker")
async def fixture_torrent_checker(mock_dlmgr, metadata_store):
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


@pytest.fixture(name="endpoint")
def fixture_endpoint(torrent_checker, needle_in_haystack_mds, tribler_db) -> DatabaseEndpoint:
    return DatabaseEndpoint(torrent_checker.download_manager, torrent_checker, needle_in_haystack_mds,
                            tribler_db=tribler_db)


async def test_check_torrent_health(rest_api):
    """
    Test the endpoint to fetch the health of a chant-managed, infohash-only torrent
    """
    infohash = b'a' * 20
    url = f'metadata/torrents/{hexlify(infohash)}/health?timeout={TORRENT_CHECK_TIMEOUT}'
    json_response = await do_request(rest_api, url)
    assert json_response == {'checking': True}


async def test_check_torrent_health_no_checker(rest_api, endpoint):
    """
    Test checking health without a torrent checker.
    """
    endpoint.torrent_checker = None
    infohash = b'a' * 20
    url = f'metadata/torrents/{hexlify(infohash)}/health?timeout={TORRENT_CHECK_TIMEOUT}'
    json_response = await do_request(rest_api, url)
    assert json_response == {'checking': False}


async def test_check_torrent_query(rest_api):
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
                "statements": []
            }
    fake_state = Mock(return_value=Mock(get_progress=Mock(return_value=0.5)))
    metadata_store.get_entries = Mock(return_value=[Mock(to_simple_dict=Mock(return_value=fake_entry.copy()))])
    endpoint.tag_rules_processor = Mock(process_queue=AsyncMock())
    endpoint.download_manager.get_download = Mock(return_value=Mock(get_state=fake_state))
    response = await do_request(rest_api, "metadata/torrents/popular")

    endpoint.tag_rules_processor.process_queue.assert_called_once()
    assert response == {'results': [{**fake_entry, **{"progress": 0.5}}], 'first': 1, 'last': 50}


async def test_get_popular_torrents_filter_xxx(rest_api, endpoint, metadata_store):
    """
    Test that the endpoint responds with its known entries with xxx statements stripped, if requested.
    """
    fake_entry = {
                "name": next(iter(default_xxx_filter.xxx_terms)),
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
                "statements": [next(iter(default_xxx_filter.xxx_terms))]
            }
    fake_state = Mock(return_value=Mock(get_progress=Mock(return_value=0.5)))
    metadata_store.get_entries = Mock(return_value=[Mock(to_simple_dict=Mock(return_value=fake_entry.copy()))])
    endpoint.tag_rules_processor = Mock(process_queue=AsyncMock())
    endpoint.download_manager.get_download = Mock(return_value=Mock(get_state=fake_state))
    response = await do_request(rest_api, "metadata/torrents/popular", params={"hide_xxx": 1})

    endpoint.tag_rules_processor.process_queue.assert_called_once()
    fake_entry["statements"] = []  # Should be stripped
    assert response == {'results': [{**fake_entry, **{"progress": 0.5}}], 'first': 1, 'last': 50}


async def test_get_popular_torrents_no_db(rest_api, endpoint, metadata_store):
    """
    Test that the endpoint responds with its known entries with statements intact, if no db is present.
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
                "statements": [next(iter(default_xxx_filter.xxx_terms))]
            }
    fake_state = Mock(return_value=Mock(get_progress=Mock(return_value=0.5)))
    metadata_store.get_entries = Mock(return_value=[Mock(to_simple_dict=Mock(return_value=fake_entry.copy()))])
    endpoint.tag_rules_processor = Mock(process_queue=AsyncMock())
    endpoint.download_manager.get_download = Mock(return_value=Mock(get_state=fake_state))
    endpoint.tribler_db = None
    response = await do_request(rest_api, "metadata/torrents/popular")

    endpoint.tag_rules_processor.process_queue.assert_called_once()
    assert response == {'results': [{**fake_entry, **{"progress": 0.5}}], 'first': 1, 'last': 50}


async def test_search(rest_api):
    """
    Test a search query that should return a few new type channels
    """

    parsed = await do_request(rest_api, 'metadata/search/local?txt_filter=needle', expected_code=200)
    assert len(parsed["results"]) == 1

    parsed = await do_request(rest_api, 'metadata/search/local?txt_filter=hay', expected_code=200)
    assert len(parsed["results"]) == 50

    parsed = await do_request(rest_api, 'metadata/search/local?txt_filter=needle&type=torrent', expected_code=200)
    assert parsed["results"][0]['name'] == 'needle'

    parsed = await do_request(rest_api, 'metadata/search/local?txt_filter=needle&sort_by=name', expected_code=200)
    assert len(parsed["results"]) == 1

    parsed = await do_request(rest_api, 'metadata/search/local?txt_filter=needle%2A&sort_by=name&sort_desc=1',
                              expected_code=200)
    assert len(parsed["results"]) == 2
    assert parsed["results"][0]['name'] == "needle2"


async def test_search_by_tags(rest_api):
    def mocked_get_subjects_intersection(*_, objects: Set[str], **__):
        if objects.pop() == 'missed_tag':
            return None
        return {hexlify(os.urandom(20))}

    with patch.object(KnowledgeDataAccessLayer, 'get_subjects_intersection', wraps=mocked_get_subjects_intersection):
        parsed = await do_request(rest_api, 'metadata/search/local?txt_filter=needle&tags=real_tag', expected_code=200)

        assert len(parsed["results"]) == 0

        parsed = await do_request(rest_api, 'metadata/search/local?txt_filter=needle&tags=missed_tag',
                                  expected_code=200)
        assert len(parsed["results"]) == 1


async def test_search_with_include_total_and_max_rowid(rest_api):
    """
    Test search queries with include_total and max_rowid options
    """

    parsed = await do_request(rest_api, 'metadata/search/local?txt_filter=needle', expected_code=200)
    assert len(parsed["results"]) == 1
    assert "total" not in parsed
    assert "max_rowid" not in parsed

    parsed = await do_request(rest_api, 'metadata/search/local?txt_filter=needle&include_total=1', expected_code=200)
    assert parsed["total"] == 1
    assert parsed["max_rowid"] == 102

    parsed = await do_request(rest_api, 'metadata/search/local?txt_filter=hay&include_total=1', expected_code=200)
    assert parsed["total"] == 100
    assert parsed["max_rowid"] == 102

    parsed = await do_request(rest_api, 'metadata/search/local?txt_filter=hay', expected_code=200)
    assert len(parsed["results"]) == 50

    parsed = await do_request(rest_api, 'metadata/search/local?txt_filter=hay&max_rowid=0', expected_code=200)
    assert len(parsed["results"]) == 0

    parsed = await do_request(rest_api, 'metadata/search/local?txt_filter=hay&max_rowid=19', expected_code=200)
    assert len(parsed["results"]) == 19

    parsed = await do_request(rest_api, 'metadata/search/local?txt_filter=needle&sort_by=name', expected_code=200)
    assert len(parsed["results"]) == 1

    parsed = await do_request(rest_api, 'metadata/search/local?txt_filter=needle&sort_by=name&max_rowid=20',
                              expected_code=200)
    assert len(parsed["results"]) == 0

    parsed = await do_request(rest_api, 'metadata/search/local?txt_filter=needle&sort_by=name&max_rowid=200',
                              expected_code=200)
    assert len(parsed["results"]) == 1


async def test_completions_no_query(rest_api):
    """
    Testing whether the API returns an error 400 if no query is passed when getting search completion terms
    """
    await do_request(rest_api, 'metadata/search/completions', expected_code=400)


async def test_completions(rest_api):
    """
    Testing whether the API returns the right terms when getting search completion terms
    """
    json_response = await do_request(rest_api, 'metadata/search/completions?q=tribler', expected_code=200)
    assert json_response['completions'] == []


async def test_search_with_space(rest_api, metadata_store):
    with db_session:
        metadata_store.TorrentMetadata(title='abc', infohash=random_infohash(), public_key=b'')
        metadata_store.TorrentMetadata(title='abc.def', infohash=random_infohash(), public_key=b'')
        metadata_store.TorrentMetadata(title='abc def', infohash=random_infohash(), public_key=b'')
        metadata_store.TorrentMetadata(title='abcxyz def', infohash=random_infohash(), public_key=b'')
        metadata_store.TorrentMetadata(title='abc defxyz', infohash=random_infohash(), public_key=b'')

    s1 = to_fts_query("abc")
    assert s1 == '"abc"'

    s2 = to_fts_query("abc def")
    assert s2 == '"abc" "def"'

    ss2 = to_fts_query(s2)
    assert ss2 == s2

    parsed = await do_request(rest_api, f'metadata/search/local?txt_filter={s1}', expected_code=200)
    results = {item["name"] for item in parsed["results"]}
    assert results == {'abc', 'abc.def', 'abc def', 'abc defxyz'}

    parsed = await do_request(rest_api, f'metadata/search/local?txt_filter={s2}', expected_code=200)
    results = {item["name"] for item in parsed["results"]}
    assert results == {'abc.def', 'abc def'}  # but not 'abcxyz def'


async def test_single_snippet_in_search(rest_api, metadata_store):
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
        results = await do_request(rest_api, f'metadata/search/local?txt_filter={s1}', expected_code=200)

        assert len(results["results"]) == 1
        snippet = results["results"][0]
        assert snippet["type"] == SNIPPET
        assert snippet["torrents"] == 1
        assert len(snippet["torrents_in_snippet"]) == 1
        assert snippet["torrents_in_snippet"][0]["infohash"] == hexlify(content_ih)


async def test_multiple_snippets_in_search(rest_api, metadata_store):
    """
    Test two snippets with two torrents in each snippet.
    """
    with db_session:
        infohashes = [random_infohash() for _ in range(5)]
        for ind, infohash in enumerate(infohashes):
            torrent_state = metadata_store.TorrentState(infohash=infohash, seeders=ind)
            metadata_store.TorrentMetadata(title=f'abc {ind}', infohash=infohash, health=torrent_state, public_key=b'')

    def mocked_get_objects(*__, subject=None, **___) -> List[str]:
        subject = unhexlify(subject)
        if subject in {infohashes[0], infohashes[1]}:
            return ["Content item 1"]
        if subject in {infohashes[2], infohashes[3]}:
            return ["Content item 2"]
        return []

    with patch.object(KnowledgeDataAccessLayer, 'get_objects', wraps=mocked_get_objects):
        s1 = to_fts_query("abc")
        parsed = await do_request(rest_api, f'metadata/search/local?txt_filter={s1}', expected_code=200)
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


def test_build_snippets_no_infohash(endpoint: DatabaseEndpoint):
    """ Test building snippets without infohash. The `build_snippets` should return the same results."""
    search_results = [{'dictionary': 'without infohash'}]
    result = endpoint.build_snippets(search_results)
    assert result == search_results
