from __future__ import annotations

from asyncio import sleep
from typing import Callable
from unittest.mock import AsyncMock, Mock, call

from ipv8.test.base import TestBase
from ipv8.test.REST.rest_base import MockRequest, response_to_json
from multidict import MultiDict, MultiDictProxy

from tribler.core.database.restapi.database_endpoint import DatabaseEndpoint, parse_bool
from tribler.core.database.serialization import REGULAR_TORRENT
from tribler.core.restapi.rest_endpoint import HTTP_BAD_REQUEST


class TestDatabaseEndpoint(TestBase):
    """
    Tests for the DatabaseEndpoint REST endpoint.
    """

    async def mds_run_now(self, callback: Callable[[], tuple[dict, int, int]]) -> tuple[dict, int, int]:
        """
        Run an mds callback immediately.
        """
        await sleep(0)
        return callback()

    def test_sanitize(self) -> None:
        """
        Test if parameters are properly sanitized.
        """
        soiled = MultiDictProxy(MultiDict([("first", "7"), ("last", "42"), ("sort_by", "name"), ("sort_desc", "0"),
                                           ("hide_xxx", "0"), ("category", "TEST"), ("origin_id", "13"),
                                           ("tags", "tag1"), ("tags", "tag2"), ("tags", "tag3"),
                                           ("max_rowid", "1337"), ("channel_pk", "AA")]))

        sanitized = DatabaseEndpoint.sanitize_parameters(soiled)

        self.assertEqual(7, sanitized["first"])
        self.assertEqual(42, sanitized["last"])
        self.assertEqual("title", sanitized["sort_by"])
        self.assertFalse(sanitized["sort_desc"])
        self.assertFalse(sanitized["hide_xxx"])
        self.assertEqual("TEST", sanitized["category"])
        self.assertEqual(13, sanitized["origin_id"])
        self.assertEqual(["tag1", "tag2", "tag3"], sanitized["tags"])
        self.assertEqual(1337, sanitized["max_rowid"])
        self.assertEqual(b"\xaa", sanitized["channel_pk"])

    def test_parse_bool(self) -> None:
        """
        Test if parse bool fulfills its promises.
        """
        self.assertTrue(parse_bool("true"))
        self.assertTrue(parse_bool("1"))
        self.assertFalse(parse_bool("false"))
        self.assertFalse(parse_bool("0"))

    async def test_get_torrent_health_bad_timeout(self) -> None:
        """
        Test if a bad timeout value in get_torrent_health leads to a HTTP_BAD_REQUEST status.
        """
        endpoint = DatabaseEndpoint()
        request = MockRequest("/metadata/torrents/AA/health", query={"timeout": "AA"}, match_info={"infohash": "AA"})
        request.context = [endpoint.mds]

        response = await endpoint.get_torrent_health(request)

        self.assertEqual(HTTP_BAD_REQUEST, response.status)

    async def test_get_torrent_health_no_checker(self) -> None:
        """
        Test if calling get_torrent_health without a torrent checker leads to a false checking status.
        """
        endpoint = DatabaseEndpoint()
        request = MockRequest("/metadata/torrents/AA/health", match_info={"infohash": "AA"})
        request.context = [endpoint.mds]

        response = await endpoint.get_torrent_health(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertFalse(response_body_json["checking"])

    async def test_get_torrent_health(self) -> None:
        """
        Test if calling get_torrent_health with a valid request leads to a true checking status.
        """
        endpoint = DatabaseEndpoint()
        check_torrent_health = AsyncMock()
        endpoint.torrent_checker = Mock(check_torrent_health=check_torrent_health)
        request = MockRequest("/metadata/torrents/AA/health", match_info={"infohash": "AA"})
        request.context = [endpoint.mds]

        response = await endpoint.get_torrent_health(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertTrue(response_body_json["checking"])
        self.assertEqual(call(b'\xaa', timeout=20, scrape_now=True), check_torrent_health.call_args)

    def test_add_download_progress_to_metadata_list(self) -> None:
        """
        Test if progress can be added to an existing metadata dict.
        """
        metadata = {"type": REGULAR_TORRENT, "infohash": "AA"}
        download = Mock(get_state=Mock(return_value=Mock(get_progress=Mock(return_value=1.0))),
                        tdef=Mock(infohash="AA"))
        endpoint = DatabaseEndpoint()
        endpoint.download_manager = Mock(get_download=Mock(return_value=download), metainfo_requests=[])
        endpoint.add_download_progress_to_metadata_list([metadata])

        self.assertEqual(1.0, metadata["progress"])

    def test_add_download_progress_to_metadata_list_none(self) -> None:
        """
        Test if progress is not added to an existing metadata dict if no download exists.
        """
        metadata = {"type": REGULAR_TORRENT, "infohash": "AA"}
        endpoint = DatabaseEndpoint()
        endpoint.download_manager = Mock(get_download=Mock(return_value=None), metainfo_requests=[])
        endpoint.add_download_progress_to_metadata_list([metadata])

        self.assertNotIn("progress", metadata)

    def test_add_download_progress_to_metadata_list_metainfo_requests(self) -> None:
        """
        Test if progress is not added to an existing metadata dict if it is in metainfo_requests.
        """
        metadata = {"type": REGULAR_TORRENT, "infohash": "AA"}
        download = Mock(get_state=Mock(return_value=Mock(get_progress=Mock(return_value=1.0))),
                        tdef=Mock(infohash="AA"))
        endpoint = DatabaseEndpoint()
        endpoint.download_manager = Mock(get_download=Mock(return_value=download), metainfo_requests=["AA"])
        endpoint.add_download_progress_to_metadata_list([metadata])

        self.assertNotIn("progress", metadata)

    async def test_local_search_bad_query(self) -> None:
        """
        Test if a bad value leads to a bad request status.
        """
        endpoint = DatabaseEndpoint()
        request = MockRequest("/api/metadata/search/local", query={"fts_text": "", "first": "bla"})
        request.context = [endpoint.mds]

        response = await endpoint.local_search(request)

        self.assertEqual(HTTP_BAD_REQUEST, response.status)

    async def test_local_search_errored_search(self) -> None:
        """
        Test if a search that threw an Exception leads to a bad request status.

        The exception here stems from the ``mds`` being set to ``None``.
        """
        endpoint = DatabaseEndpoint()
        endpoint.tribler_db = Mock()
        request = MockRequest("/api/metadata/search/local", query={"fts_text": ""})
        request.context = [endpoint.mds]

        response = await endpoint.local_search(request)

        self.assertEqual(HTTP_BAD_REQUEST, response.status)

    async def test_local_search(self) -> None:
        """
        Test if performing a local search returns mds results.
        """
        endpoint = DatabaseEndpoint()
        endpoint.tribler_db = Mock()
        endpoint.mds = Mock(run_threaded=self.mds_run_now, get_total_count=Mock(), get_max_rowid=Mock(),
                            get_entries=Mock(return_value=[Mock(to_simple_dict=Mock(return_value={"test": "test",
                                                                                                  "type": -1}))]))
        request = MockRequest("/api/metadata/search/local", query={"fts_text": ""})
        request.context = [endpoint.mds]

        response = await endpoint.local_search(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertEqual("test", response_body_json["results"][0]["test"])
        self.assertEqual(1, response_body_json["first"])
        self.assertEqual(50, response_body_json["last"])
        self.assertEqual(None, response_body_json["sort_by"])
        self.assertEqual(True, response_body_json["sort_desc"])

    async def test_local_search_include_total(self) -> None:
        """
        Test if performing a local search with requested total, includes a total.
        """
        endpoint = DatabaseEndpoint()
        endpoint.tribler_db = Mock()
        endpoint.mds = Mock(run_threaded=self.mds_run_now, get_total_count=Mock(return_value=1),
                            get_max_rowid=Mock(return_value=7),
                            get_entries=Mock(return_value=[Mock(to_simple_dict=Mock(return_value={"test": "test",
                                                                                                  "type": -1}))]))
        request = MockRequest("/api/metadata/search/local", query={"fts_text": "",
                                                                   "include_total": "I would like this"})
        request.context = [endpoint.mds]

        response = await endpoint.local_search(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertEqual("test", response_body_json["results"][0]["test"])
        self.assertEqual(1, response_body_json["first"])
        self.assertEqual(50, response_body_json["last"])
        self.assertEqual(None, response_body_json["sort_by"])
        self.assertEqual(True, response_body_json["sort_desc"])
        self.assertEqual(1, response_body_json["total"])
        self.assertEqual(7, response_body_json["max_rowid"])

    async def test_completions_bad_query(self) -> None:
        """
        Test if a missing query leads to a bad request status.
        """
        endpoint = DatabaseEndpoint()
        request = MockRequest("/api/metadata/search/completions")
        request.context = [endpoint.mds]

        response = await endpoint.completions(request)

        self.assertEqual(HTTP_BAD_REQUEST, response.status)

    async def test_completions_lowercase_search(self) -> None:
        """
        Test if a normal lowercase search leads to results.
        """
        endpoint = DatabaseEndpoint()
        endpoint.mds = Mock(get_auto_complete_terms=Mock(return_value=["test1", "test2"]))
        request = MockRequest("/api/metadata/search/completions", query={"q": "test"})
        request.context = [endpoint.mds]

        response = await endpoint.completions(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertEqual(["test1", "test2"], response_body_json["completions"])
        self.assertEqual(call("test", max_terms=5), endpoint.mds.get_auto_complete_terms.call_args)

    async def test_completions_mixed_case_search(self) -> None:
        """
        Test if a mixed case search leads to results.
        """
        endpoint = DatabaseEndpoint()
        endpoint.mds = Mock(get_auto_complete_terms=Mock(return_value=["test1", "test2"]))
        request = MockRequest("/api/metadata/search/completions", query={"q": "TeSt"})
        request.context = [endpoint.mds]

        response = await endpoint.completions(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertEqual(["test1", "test2"], response_body_json["completions"])
        self.assertEqual(call("test", max_terms=5), endpoint.mds.get_auto_complete_terms.call_args)
