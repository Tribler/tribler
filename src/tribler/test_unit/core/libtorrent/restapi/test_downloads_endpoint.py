"""
Keep this text for the test_stream test.
"""
from __future__ import annotations

from io import StringIO
from pathlib import Path
from unittest.mock import AsyncMock, Mock, call, patch

from aiohttp.web_urldispatcher import UrlMappingMatchInfo
from configobj import ConfigObj
from ipv8.test.base import TestBase
from ipv8.test.REST.rest_base import BodyCapture, MockRequest, response_to_bytes, response_to_json
from validate import Validator

from tribler.core.libtorrent.download_manager.download import Download
from tribler.core.libtorrent.download_manager.download_config import SPEC_CONTENT, DownloadConfig
from tribler.core.libtorrent.download_manager.stream import Stream
from tribler.core.libtorrent.restapi.downloads_endpoint import DownloadsEndpoint
from tribler.core.libtorrent.torrentdef import TorrentDef, TorrentDefNoMetainfo
from tribler.core.restapi.rest_endpoint import HTTP_BAD_REQUEST, HTTP_INTERNAL_SERVER_ERROR, HTTP_NOT_FOUND
from tribler.test_unit.core.libtorrent.mocks import TORRENT_WITH_DIRS, TORRENT_WITH_DIRS_CONTENT, TORRENT_WITH_VIDEO
from tribler.test_unit.mocks import MockTriblerConfigManager


class StreamRequest(MockRequest):
    """
    A MockRequest that mimics StreamRequests.
    """

    __slots__ = ['http_range']

    def __init__(self, query: dict, infohash: str, fileindex: int, **kwargs) -> None:
        """
        Create a new StreamRequest.
        """
        super().__init__(f"/downloads/{infohash}/stream/{fileindex}", "GET", query)
        self._infohash = infohash
        self._fileindex = fileindex
        self._payload_writer = BodyCapture()
        self.http_range = Mock(**kwargs)

    def get_transmitted(self) -> bytes:
        """
        Get the received bytes from the writer.
        """
        return self._payload_writer.getvalue()

    @property
    def match_info(self) -> UrlMappingMatchInfo:
        """
        Get the match info (the infohash in the url).
        """
        return UrlMappingMatchInfo({"infohash": self._infohash, "fileindex": self._fileindex}, Mock())


class TestDownloadsEndpoint(TestBase):
    """
    Tests for the DownloadsEndpoint class.
    """

    def setUp(self) -> None:
        """
        Create a mocked DownloadManager and a DownloadsEndpoint.
        """
        super().setUp()
        self.download_manager = Mock()
        self.download_manager.config = MockTriblerConfigManager()
        self.endpoint = DownloadsEndpoint(self.download_manager)

    def set_loaded_downloads(self, downloads: list[Download] | None = None) -> None:
        """
        Set the status for all checkpoints being loaded.
        """
        self.download_manager.get_downloads = Mock(return_value=downloads or [])
        self.download_manager.checkpoints_count = len(downloads)
        self.download_manager.checkpoints_loaded = len(downloads)
        self.download_manager.all_checkpoints_are_loaded = True

    def create_mock_download(self) -> Download:
        """
        Create a mocked Download.
        """
        defaults = ConfigObj(StringIO(SPEC_CONTENT))
        conf = ConfigObj()
        conf.configspec = defaults
        conf.validate(Validator())
        config = DownloadConfig(conf)
        config.set_dest_dir(Path(""))
        return Download(TorrentDefNoMetainfo(b"\x01" * 20, b"test"), None, config, hidden=False,
                        checkpoint_disabled=True)

    async def test_get_downloads_unloaded(self) -> None:
        """
        Test if a clean response is returned if the checkpoints are not loaded yet.
        """
        self.download_manager.checkpoints_count = 1
        self.download_manager.checkpoints_loaded = 0
        self.download_manager.all_checkpoints_are_loaded = False
        self.download_manager.get_downloads = Mock(return_value=[])
        request = MockRequest("/api/downloads", query={})

        response = await self.endpoint.get_downloads(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertEqual([], response_body_json["downloads"])
        self.assertEqual(1, response_body_json["checkpoints"]["total"])
        self.assertEqual(0, response_body_json["checkpoints"]["loaded"])
        self.assertFalse(response_body_json["checkpoints"]["all_loaded"])

    async def test_get_downloads_no_downloads(self) -> None:
        """
        Test if an empty list is returned if there are no downloads.
        """
        self.set_loaded_downloads([])
        request = MockRequest("/api/downloads", query={})

        response = await self.endpoint.get_downloads(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertEqual([], response_body_json["downloads"])
        self.assertEqual(0, response_body_json["checkpoints"]["total"])
        self.assertEqual(0, response_body_json["checkpoints"]["loaded"])
        self.assertTrue(response_body_json["checkpoints"]["all_loaded"])

    async def test_get_downloads_hidden_download(self) -> None:
        """
        Test if an empty list is returned if there are only hidden downloads.
        """
        self.set_loaded_downloads([Download(TorrentDefNoMetainfo(b"\x01" * 20, b"test"), None, Mock(),
                                            hidden=True, checkpoint_disabled=True)])
        request = MockRequest("/api/downloads", query={})

        response = await self.endpoint.get_downloads(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertEqual([], response_body_json["downloads"])
        self.assertEqual(1, response_body_json["checkpoints"]["total"])
        self.assertEqual(1, response_body_json["checkpoints"]["loaded"])
        self.assertTrue(response_body_json["checkpoints"]["all_loaded"])

    async def test_get_downloads_normal_download(self) -> None:
        """
        Test if the information of a normal download is correctly presented.
        """
        self.set_loaded_downloads([self.create_mock_download()])
        request = MockRequest("/api/downloads", query={})

        response = await self.endpoint.get_downloads(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertFalse(response_body_json["downloads"][0]["anon_download"])
        self.assertEqual(".", response_body_json["downloads"][0]["destination"])
        self.assertEqual("", response_body_json["downloads"][0]["error"])
        self.assertEqual(0.0, response_body_json["downloads"][0]["eta"])
        self.assertEqual(0, response_body_json["downloads"][0]["hops"])
        self.assertEqual("0101010101010101010101010101010101010101", response_body_json["downloads"][0]["infohash"])
        self.assertEqual(0, response_body_json["downloads"][0]["max_download_speed"])
        self.assertEqual(0, response_body_json["downloads"][0]["max_upload_speed"])
        self.assertEqual("test", response_body_json["downloads"][0]["name"])
        self.assertEqual(0, response_body_json["downloads"][0]["num_connected_peers"])
        self.assertEqual(0, response_body_json["downloads"][0]["num_connected_seeds"])
        self.assertEqual(0, response_body_json["downloads"][0]["num_peers"])
        self.assertEqual(0, response_body_json["downloads"][0]["num_seeds"])
        self.assertEqual(0, response_body_json["downloads"][0]["progress"])
        self.assertEqual(0, response_body_json["downloads"][0]["all_time_ratio"])
        self.assertFalse(response_body_json["downloads"][0]["safe_seeding"])
        self.assertEqual(0, response_body_json["downloads"][0]["size"])
        self.assertEqual(0, response_body_json["downloads"][0]["speed_down"])
        self.assertEqual(0, response_body_json["downloads"][0]["speed_up"])
        self.assertEqual("STOPPED", response_body_json["downloads"][0]["status"])
        self.assertEqual(5, response_body_json["downloads"][0]["status_code"])
        self.assertEqual(0, response_body_json["downloads"][0]["time_added"])
        self.assertEqual(0, response_body_json["downloads"][0]["all_time_download"])
        self.assertEqual(0, response_body_json["downloads"][0]["total_pieces"])
        self.assertEqual(0, response_body_json["downloads"][0]["all_time_upload"])
        self.assertEqual([], response_body_json["downloads"][0]["trackers"])
        self.assertEqual(1, response_body_json["checkpoints"]["total"])
        self.assertEqual(1, response_body_json["checkpoints"]["loaded"])
        self.assertTrue(response_body_json["checkpoints"]["all_loaded"])

    async def test_get_downloads_filter_download_pass(self) -> None:
        """
        Test if the information of a download that passes the filter is correctly presented.
        """
        download = self.create_mock_download()
        download.handle = Mock(is_valid=Mock(return_value=False), status=Mock(return_value=Mock(pieces=[False])))
        self.set_loaded_downloads([download])
        request = MockRequest("/api/downloads", query={"infohash": "01" * 20, "get_peers": "1",
                                                       "get_pieces": "1", "get_availability": "1"})

        response = await self.endpoint.get_downloads(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertEqual("01" * 20, response_body_json["downloads"][0]["infohash"])
        self.assertEqual([], response_body_json["downloads"][0]["peers"])
        self.assertEqual("", response_body_json["downloads"][0]["pieces"])
        self.assertEqual(0, response_body_json["downloads"][0]["availability"])

    async def test_get_downloads_filter_download_fail(self) -> None:
        """
        Test if the information of a download that does not pass the filter is correctly presented.
        """
        download = self.create_mock_download()
        download.handle = Mock(is_valid=Mock(return_value=False), status=Mock(return_value=Mock(pieces=[False])))
        self.set_loaded_downloads([download])
        request = MockRequest("/api/downloads", query={"infohash": "02" * 20, "get_peers": "1",
                                                       "get_pieces": "1", "get_availability": "1"})

        response = await self.endpoint.get_downloads(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertEqual("01" * 20, response_body_json["downloads"][0]["infohash"])
        self.assertNotIn("peers", response_body_json["downloads"][0])
        self.assertNotIn("pieces", response_body_json["downloads"][0])
        self.assertNotIn("availability", response_body_json["downloads"][0])

    async def test_get_downloads_stream_download(self) -> None:
        """
        Test if the information of a steaming download is correctly presented.
        """
        download = self.create_mock_download()
        download.handle = Mock(is_valid=Mock(return_value=False))
        download.stream = Stream(download)
        download.stream.close()
        self.set_loaded_downloads([download])
        request = MockRequest("/api/downloads", query={})

        response = await self.endpoint.get_downloads(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertFalse(response_body_json["downloads"][0]["anon_download"])
        self.assertEqual(0.0, response_body_json["downloads"][0]["vod_prebuffering_progress"])
        self.assertEqual(0.0, response_body_json["downloads"][0]["vod_prebuffering_progress_consec"])
        self.assertEqual(0.0, response_body_json["downloads"][0]["vod_header_progress"])
        self.assertEqual(0.0, response_body_json["downloads"][0]["vod_footer_progress"])

    async def test_add_download_no_uri(self) -> None:
        """
        Test if a graceful error is returned when no uri is given.
        """
        request = MockRequest("/api/downloads", "PUT", {})

        response = await self.endpoint.add_download(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_BAD_REQUEST, response.status)
        self.assertEqual("uri parameter missing", response_body_json["error"]["message"])

    async def test_add_download_unsafe_anon_error(self) -> None:
        """
        Test if a graceful error is returned when safe seeding is not enabled in anonymous mode.
        """
        download = self.create_mock_download()
        request = MockRequest("/api/downloads", "PUT", {"uri": "http://127.0.0.1/file",
                                                        "anon_hops": 1, "safe_seeding": 0})

        with patch("tribler.core.libtorrent.download_manager.download_config.DownloadConfig.from_defaults",
                   lambda _: download.config):
            response = await self.endpoint.add_download(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_BAD_REQUEST, response.status)
        self.assertEqual("Cannot set anonymous download without safe seeding enabled",
                         response_body_json["error"]["message"])

    async def test_add_download_default_parameters(self) -> None:
        """
        Test if the default parameters are set when adding a download.
        """
        download = self.create_mock_download()
        self.download_manager.start_download_from_uri = AsyncMock(return_value=download)
        request = MockRequest("/api/downloads", "PUT", {"uri": "http://127.0.0.1/file"})

        with patch("tribler.core.libtorrent.download_manager.download_config.DownloadConfig.from_defaults",
                   lambda _: download.config):
            response = await self.endpoint.add_download(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertTrue(response_body_json["started"])
        self.assertEqual("01" * 20, response_body_json["infohash"])
        self.assertEqual(0, download.config.get_hops())
        self.assertFalse(download.config.get_safe_seeding())
        self.assertEqual(Path(""), download.config.get_dest_dir())
        self.assertEqual([], download.config.get_selected_files())

    async def test_add_download_custom_parameters(self) -> None:
        """
        Test if the custom parameters are set when adding a download.
        """
        download = self.create_mock_download()
        self.download_manager.start_download_from_uri = AsyncMock(return_value=download)
        request = MockRequest("/api/downloads", "PUT", {"uri": "http://127.0.0.1/file", "safe_seeding": 1,
                                                        "selected_files": [0], "destination": "foo", "anon_hops": 1})

        with patch("tribler.core.libtorrent.download_manager.download_config.DownloadConfig.from_defaults",
                   lambda _: download.config):
            response = await self.endpoint.add_download(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertTrue(response_body_json["started"])
        self.assertEqual("01" * 20, response_body_json["infohash"])
        self.assertEqual(1, download.config.get_hops())
        self.assertTrue(download.config.get_safe_seeding())
        self.assertEqual(Path("foo"), download.config.get_dest_dir())
        self.assertEqual([0], download.config.get_selected_files())

    async def test_add_download_failed(self) -> None:
        """
        Test if a graceful error is returned when adding a download failed.
        """
        download = self.create_mock_download()
        self.download_manager.start_download_from_uri = AsyncMock(side_effect=Exception("invalid uri"))
        request = MockRequest("/api/downloads", "PUT", {"uri": "http://127.0.0.1/file"})

        with patch("tribler.core.libtorrent.download_manager.download_config.DownloadConfig.from_defaults",
                   lambda _: download.config):
            response = await self.endpoint.add_download(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_INTERNAL_SERVER_ERROR, response.status)
        self.assertEqual("invalid uri", response_body_json["error"]["message"])

    async def test_delete_download_no_remove_data(self) -> None:
        """
        Test if a graceful error is returned when no remove data is supplied when deleting a download.
        """
        request = MockRequest("/api/downloads/" + "01" * 20, "DELETE", {}, {"infohash": "01" * 20})

        response = await self.endpoint.delete_download(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_BAD_REQUEST, response.status)
        self.assertEqual("remove_data parameter missing", response_body_json["error"]["message"])

    async def test_delete_download_no_download(self) -> None:
        """
        Test if a graceful error is returned when no download is found for removal.
        """
        self.download_manager.get_download = Mock(return_value=None)
        request = MockRequest("/api/downloads/" + "01" * 20, "DELETE", {"remove_data": False}, {"infohash": "01" * 20})

        response = await self.endpoint.delete_download(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_NOT_FOUND, response.status)
        self.assertEqual("this download does not exist", response_body_json["error"]["message"])

    async def test_delete_download_no_data(self) -> None:
        """
        Test if the requested download is removed without removing data on request.
        """
        download = self.create_mock_download()
        self.download_manager.get_download = Mock(return_value=download)
        self.download_manager.remove_download = AsyncMock()
        request = MockRequest("/api/downloads/" + "01" * 20, "DELETE", {"remove_data": False}, {"infohash": "01" * 20})

        response = await self.endpoint.delete_download(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertTrue(response_body_json["removed"])
        self.assertEqual("01" * 20, response_body_json["infohash"])
        self.assertEqual(call(download, remove_content=False), self.download_manager.remove_download.call_args)

    async def test_delete_download_with_data(self) -> None:
        """
        Test if the requested download and its data is removed on request.
        """
        download = self.create_mock_download()
        self.download_manager.get_download = Mock(return_value=download)
        self.download_manager.remove_download = AsyncMock()
        request = MockRequest("/api/downloads/" + "01" * 20, "DELETE", {"remove_data": True}, {"infohash": "01" * 20})

        response = await self.endpoint.delete_download(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertTrue(response_body_json["removed"])
        self.assertEqual("01" * 20, response_body_json["infohash"])
        self.assertEqual(call(download, remove_content=True), self.download_manager.remove_download.call_args)

    async def test_delete_download_delete_failed(self) -> None:
        """
        Test if a graceful error is returned when the deletion of an existing download fails.
        """
        download = self.create_mock_download()
        self.download_manager.get_download = Mock(return_value=download)
        self.download_manager.remove_download = AsyncMock(side_effect=OSError)
        request = MockRequest("/api/downloads/" + "01" * 20, "DELETE", {"remove_data": False}, {"infohash": "01" * 20})

        response = await self.endpoint.delete_download(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_INTERNAL_SERVER_ERROR, response.status)
        self.assertTrue(response_body_json["error"]["handled"])
        self.assertEqual("OSError: ", response_body_json["error"]["message"])

    async def test_update_download_no_download(self) -> None:
        """
        Test if a graceful error is returned when no download is found to update.
        """
        self.download_manager.get_download = Mock(return_value=None)
        request = MockRequest("/api/downloads/" + "01" * 20, "PATCH", {}, {"infohash": "01" * 20})

        response = await self.endpoint.update_download(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_NOT_FOUND, response.status)
        self.assertEqual("this download does not exist", response_body_json["error"]["message"])

    async def test_update_download_anon_hops_garbage(self) -> None:
        """
        Test if anon hops can only exist as the only parameter.
        """
        request = MockRequest("/api/downloads/" + "01" * 20, "PATCH", {"anon_hops": 1, "foo": "bar"},
                              {"infohash": "01" * 20})

        response = await self.endpoint.update_download(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_BAD_REQUEST, response.status)
        self.assertEqual("anon_hops must be the only parameter in this request", response_body_json["error"]["message"])

    async def test_update_download_anon_hops_update(self) -> None:
        """
        Test if anon hops can be updated.
        """
        download = self.create_mock_download()
        self.download_manager.get_download = Mock(return_value=download)
        self.download_manager.update_hops = AsyncMock()
        request = MockRequest("/api/downloads/" + "01" * 20, "PATCH", {"anon_hops": 1}, {"infohash": "01" * 20})

        response = await self.endpoint.update_download(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertTrue(response_body_json["modified"])
        self.assertEqual("01" * 20, response_body_json["infohash"])

    async def test_update_download_anon_hops_update_failed(self) -> None:
        """
        Test if a graceful error is returned when updating the anon hops failed.
        """
        download = self.create_mock_download()
        self.download_manager.get_download = Mock(return_value=download)
        self.download_manager.update_hops = AsyncMock(side_effect=OSError)
        request = MockRequest("/api/downloads/" + "01" * 20, "PATCH", {"anon_hops": 1}, {"infohash": "01" * 20})

        response = await self.endpoint.update_download(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_INTERNAL_SERVER_ERROR, response.status)
        self.assertTrue(response_body_json["error"]["handled"])
        self.assertEqual("OSError: ", response_body_json["error"]["message"])

    async def test_update_download_selected_files_out_of_range(self) -> None:
        """
        Test if a graceful error is returned when the selected files are out of range.
        """
        download = self.create_mock_download()
        download.tdef.metainfo = {b"info": {b"files": [{b"path": {b"hi.txt"}, b"length": 0}]}}
        self.download_manager.get_download = Mock(return_value=download)
        request = MockRequest("/api/downloads/" + "01" * 20, "PATCH", {"selected_files": [99999999999]},
                              {"infohash": "01" * 20})

        response = await self.endpoint.update_download(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_BAD_REQUEST, response.status)
        self.assertEqual("index out of range", response_body_json["error"]["message"])

    async def test_update_download_selected_files(self) -> None:
        """
        Test if the selected files of a download can be updated.
        """
        download = self.create_mock_download()
        download.tdef.metainfo = {b"info": {b"files": [{b"path": {b"hi.txt"}, b"length": 0}]}}
        self.download_manager.get_download = Mock(return_value=download)
        request = MockRequest("/api/downloads/" + "01" * 20, "PATCH", {"selected_files": [0]}, {"infohash": "01" * 20})

        response = await self.endpoint.update_download(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertTrue(response_body_json["modified"])
        self.assertEqual("01" * 20, response_body_json["infohash"])

    async def test_update_download_unknown_state(self) -> None:
        """
        Test if a graceful error is returned when a download is set to an unknown state.
        """
        download = self.create_mock_download()
        self.download_manager.get_download = Mock(return_value=download)
        request = MockRequest("/api/downloads/" + "01" * 20, "PATCH", {"state": "foo"}, {"infohash": "01" * 20})

        response = await self.endpoint.update_download(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_BAD_REQUEST, response.status)
        self.assertEqual("unknown state parameter", response_body_json["error"]["message"])

    async def test_update_download_state_resume(self) -> None:
        """
        Test if a download can be set to the resume state.
        """
        download = self.create_mock_download()
        download.config.set_user_stopped(True)
        self.download_manager.get_download = Mock(return_value=download)
        request = MockRequest("/api/downloads/" + "01" * 20, "PATCH", {"state": "resume"}, {"infohash": "01" * 20})

        response = await self.endpoint.update_download(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertTrue(response_body_json["modified"])
        self.assertEqual("01" * 20, response_body_json["infohash"])
        self.assertFalse(download.config.get_user_stopped())

    async def test_update_download_state_stop(self) -> None:
        """
        Test if a download can be set to the stopped state.
        """
        download = self.create_mock_download()
        download.config.set_user_stopped(False)
        self.download_manager.get_download = Mock(return_value=download)
        request = MockRequest("/api/downloads/" + "01" * 20, "PATCH", {"state": "stop"}, {"infohash": "01" * 20})

        response = await self.endpoint.update_download(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertTrue(response_body_json["modified"])
        self.assertEqual("01" * 20, response_body_json["infohash"])
        self.assertTrue(download.config.get_user_stopped())

    async def test_update_download_state_recheck(self) -> None:
        """
        Test if a download can be set to the recheck state.
        """
        download = self.create_mock_download()
        download.tdef = Mock(get_infohash=Mock(return_value=b"\x01" * 20))
        download.handle = Mock(is_valid=Mock(return_value=True))
        self.download_manager.get_download = Mock(return_value=download)
        request = MockRequest("/api/downloads/" + "01" * 20, "PATCH", {"state": "recheck"}, {"infohash": "01" * 20})

        response = await self.endpoint.update_download(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertTrue(response_body_json["modified"])
        self.assertEqual("01" * 20, response_body_json["infohash"])
        self.assertEqual(call(), download.handle.force_recheck.call_args)

    async def test_update_download_state_move_storage_no_dest_dir(self) -> None:
        """
        Test if a graceful error is returned when no dest dir is specified when setting the move storage state.
        """
        download = self.create_mock_download()
        self.download_manager.get_download = Mock(return_value=download)
        request = MockRequest("/api/downloads/" + "01" * 20, "PATCH",
                              {"state": "move_storage", "dest_dir": "I don't exist"}, {"infohash": "01" * 20})

        response = await self.endpoint.update_download(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_BAD_REQUEST, response.status)
        self.assertEqual("Target directory (I don't exist) does not exist", response_body_json["error"]["message"])

    async def test_update_download_state_move_storage(self) -> None:
        """
        Test if a download can be set to the move_storage state.
        """
        download = self.create_mock_download()
        download.tdef = Mock(get_infohash=Mock(return_value=b"\x01" * 20))
        download.handle = Mock(is_valid=Mock(return_value=True))
        self.download_manager.get_download = Mock(return_value=download)
        request = MockRequest("/api/downloads/" + "01" * 20, "PATCH",
                              {"state": "move_storage", "dest_dir": str(Path(__file__).parent)},
                              {"infohash": "01" * 20})

        response = await self.endpoint.update_download(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertTrue(response_body_json["modified"])
        self.assertEqual("01" * 20, response_body_json["infohash"])
        self.assertEqual(call(str(Path(__file__).parent)), download.handle.move_storage.call_args)

    async def test_update_download_nothing(self) -> None:
        """
        Test if a download can be updated with nothing.
        """
        download = self.create_mock_download()
        self.download_manager.get_download = Mock(return_value=download)
        request = MockRequest("/api/downloads/" + "01" * 20, "PATCH", {}, {"infohash": "01" * 20})

        response = await self.endpoint.update_download(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertTrue(response_body_json["modified"])
        self.assertEqual("01" * 20, response_body_json["infohash"])

    async def test_get_torrent_no_download(self) -> None:
        """
        Test if a graceful error is returned when no download is found.
        """
        self.download_manager.get_download = Mock(return_value=None)
        request = MockRequest(f"/api/downloads/{'01' * 20}/torrent", "GET", {}, {"infohash": "01" * 20})

        response = await self.endpoint.get_torrent(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_NOT_FOUND, response.status)
        self.assertEqual("this download does not exist", response_body_json["error"]["message"])

    async def test_get_torrent_no_torrent_data(self) -> None:
        """
        Test if a graceful error is returned when no torrent data is found.
        """
        self.download_manager.get_download = Mock(return_value=Mock(get_torrent_data=Mock(return_value=None)))
        request = MockRequest(f"/api/downloads/{'01' * 20}/torrent", "GET", {}, {"infohash": "01" * 20})

        response = await self.endpoint.get_torrent(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_NOT_FOUND, response.status)
        self.assertEqual("this download does not exist", response_body_json["error"]["message"])

    async def test_get_torrent(self) -> None:
        """
        Test if torrent data is correctly sent over on request.
        """
        download = self.create_mock_download()
        download.handle = Mock(is_valid=Mock(return_value=True), torrent_file=Mock(return_value=TORRENT_WITH_DIRS))
        self.download_manager.get_download = Mock(return_value=download)
        request = MockRequest(f"/api/downloads/{'01' * 20}/torrent", "GET", {}, {"infohash": "01" * 20})

        response = await self.endpoint.get_torrent(request)
        response_body_bytes = await response_to_bytes(response)

        self.assertEqual(200, response.status)
        self.assertEqual(TORRENT_WITH_DIRS_CONTENT, response_body_bytes)

    async def test_get_files_no_download(self) -> None:
        """
        Test if a graceful error is returned when no download is found.
        """
        self.download_manager.get_download = Mock(return_value=None)
        request = MockRequest(f"/api/downloads/{'01' * 20}/files", "GET", {}, {"infohash": "01" * 20})

        response = await self.endpoint.get_files(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_NOT_FOUND, response.status)
        self.assertEqual("this download does not exist", response_body_json["error"]["message"])

    async def test_get_files_without_path(self) -> None:
        """
        Test if the files of a download get be retrieved without specifying a starting path.
        """
        download = self.create_mock_download()
        download.tdef = TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT)
        self.download_manager.get_download = Mock(return_value=download)
        request = MockRequest(f"/api/downloads/{'01' * 20}/files", "GET", {}, {"infohash": "01" * 20})

        response = await self.endpoint.get_files(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertEqual("01" * 20, response_body_json["infohash"])
        self.assertEqual(6, len(response_body_json["files"]))

    async def test_get_files_with_path_unloaded(self) -> None:
        """
        Test if the special loading state is returned when using a starting path and an unloaded torrent.
        """
        download = self.create_mock_download()
        download.tdef = TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT)
        self.download_manager.get_download = Mock(return_value=download)
        request = MockRequest(f"/api/downloads/{'01' * 20}/files", "GET",
                              {"view_start_path": "def/file6.avi", "view_size": 2}, {"infohash": "01" * 20})

        response = await self.endpoint.get_files(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertEqual("01" * 20, response_body_json["infohash"])
        self.assertEqual(1, len(response_body_json["files"]))
        self.assertEqual(-3, response_body_json["files"][0]["index"])
        self.assertEqual("loading...", response_body_json["files"][0]["name"])
        self.assertEqual(0, response_body_json["files"][0]["size"])
        self.assertEqual(0, response_body_json["files"][0]["included"])
        self.assertEqual(0.0, response_body_json["files"][0]["progress"])

    async def test_get_files_with_path(self) -> None:
        """
        Test if the files of a download get be retrieved using a starting path.
        """
        download = self.create_mock_download()
        download.tdef = TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT)
        download.tdef.load_torrent_info()
        download.tdef.torrent_file_tree.expand(Path("torrent_create/abc"))
        self.download_manager.get_download = Mock(return_value=download)
        request = MockRequest(f"/api/downloads/{'01' * 20}/files", "GET",
                              {"view_start_path": "torrent_create", "view_size": 2}, {"infohash": "01" * 20})

        response = await self.endpoint.get_files(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertEqual("01" * 20, response_body_json["infohash"])
        self.assertEqual(2, len(response_body_json["files"]))
        self.assertEqual(-2, response_body_json["files"][0]["index"])
        self.assertEqual(Path("torrent_create/abc"), Path(response_body_json["files"][0]["name"]))
        self.assertEqual(18, response_body_json["files"][0]["size"])
        self.assertFalse(response_body_json["files"][0]["included"])
        self.assertEqual(0.0, response_body_json["files"][0]["progress"])
        self.assertEqual(0, response_body_json["files"][1]["index"])
        self.assertEqual(Path("torrent_create/abc/file2.txt"), Path(response_body_json["files"][1]["name"]))
        self.assertEqual(6, response_body_json["files"][1]["size"])
        self.assertTrue(response_body_json["files"][1]["included"])
        self.assertEqual(0.0, response_body_json["files"][1]["progress"])

    async def test_collapse_tree_directory_no_download(self) -> None:
        """
        Test if a graceful error is returned when no download is found.
        """
        self.download_manager.get_download = Mock(return_value=None)
        request = MockRequest(f"/api/downloads/{'01' * 20}/files/collapse", "GET", {}, {"infohash": "01" * 20})

        response = await self.endpoint.collapse_tree_directory(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_NOT_FOUND, response.status)
        self.assertEqual("this download does not exist", response_body_json["error"]["message"])

    async def test_collapse_tree_directory(self) -> None:
        """
        Test if a file tree directory can be collapsed.
        """
        download = self.create_mock_download()
        download.tdef = TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT)
        download.tdef.load_torrent_info()
        download.tdef.torrent_file_tree.expand(Path("torrent_create/abc"))
        self.download_manager.get_download = Mock(return_value=download)
        request = MockRequest(f"/api/downloads/{'01' * 20}/files/collapse", "GET",
                              {"path": "torrent_create/abc"}, {"infohash": "01" * 20})

        response = await self.endpoint.collapse_tree_directory(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertTrue(download.tdef.torrent_file_tree.find(Path("torrent_create/abc")).collapsed)
        self.assertEqual("torrent_create/abc", response_body_json["path"])

    async def test_expand_tree_directory_no_download(self) -> None:
        """
        Test if a graceful error is returned when no download is found.
        """
        self.download_manager.get_download = Mock(return_value=None)
        request = MockRequest(f"/api/downloads/{'01' * 20}/files/expand", "GET", {}, {"infohash": "01" * 20})

        response = await self.endpoint.expand_tree_directory(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_NOT_FOUND, response.status)
        self.assertEqual("this download does not exist", response_body_json["error"]["message"])

    async def test_expand_tree_directory(self) -> None:
        """
        Test if a file tree directory can be expanded.
        """
        download = self.create_mock_download()
        download.tdef = TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT)
        download.tdef.load_torrent_info()
        self.download_manager.get_download = Mock(return_value=download)
        request = MockRequest(f"/api/downloads/{'01' * 20}/files/expand", "GET",
                              {"path": "torrent_create/abc"}, {"infohash": "01" * 20})

        response = await self.endpoint.expand_tree_directory(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertFalse(download.tdef.torrent_file_tree.find(Path("torrent_create/abc")).collapsed)
        self.assertEqual("torrent_create/abc", response_body_json["path"])

    async def test_select_tree_path_no_download(self) -> None:
        """
        Test if a graceful error is returned when no download is found.
        """
        self.download_manager.get_download = Mock(return_value=None)
        request = MockRequest(f"/api/downloads/{'01' * 20}/files/select", "GET", {}, {"infohash": "01" * 20})

        response = await self.endpoint.select_tree_path(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_NOT_FOUND, response.status)
        self.assertEqual("this download does not exist", response_body_json["error"]["message"])

    async def test_select_tree_path(self) -> None:
        """
        Test if a tree path can be selected.
        """
        download = self.create_mock_download()
        download.handle = Mock(is_valid=Mock(return_value=True))
        download.tdef = TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT)
        download.tdef.load_torrent_info()
        self.download_manager.get_download = Mock(return_value=download)
        request = MockRequest(f"/api/downloads/{'01' * 20}/files/select", "GET",
                              {"path": "torrent_create/def/file6.avi"}, {"infohash": "01" * 20})

        response = await self.endpoint.select_tree_path(request)

        self.assertEqual(200, response.status)
        self.assertTrue(download.tdef.torrent_file_tree.find(Path("torrent_create/def/file6.avi")).selected)

    async def test_deselect_tree_path_no_download(self) -> None:
        """
        Test if a graceful error is returned when no download is found.
        """
        self.download_manager.get_download = Mock(return_value=None)
        request = MockRequest(f"/api/downloads/{'01' * 20}/files/deselect", "GET", {}, {"infohash": "01" * 20})

        response = await self.endpoint.deselect_tree_path(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_NOT_FOUND, response.status)
        self.assertEqual("this download does not exist", response_body_json["error"]["message"])

    async def test_deselect_tree_path(self) -> None:
        """
        Test if a tree path can be deselected.
        """
        download = self.create_mock_download()
        download.handle = Mock(is_valid=Mock(return_value=True))
        download.tdef = TorrentDef.load_from_memory(TORRENT_WITH_DIRS_CONTENT)
        download.tdef.load_torrent_info()
        self.download_manager.get_download = Mock(return_value=download)
        request = MockRequest(f"/api/downloads/{'01' * 20}/files/deselect", "GET",
                              {"path": "torrent_create/def/file6.avi"}, {"infohash": "01" * 20})

        response = await self.endpoint.deselect_tree_path(request)

        self.assertEqual(200, response.status)
        self.assertFalse(download.tdef.torrent_file_tree.find(Path("torrent_create/def/file6.avi")).selected)

    async def test_stream_no_download(self) -> None:
        """
        Test if a graceful error is returned when no download is found.
        """
        self.download_manager.get_download = Mock(return_value=None)

        response = await self.endpoint.stream(StreamRequest({}, "01" * 20, 0))
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_NOT_FOUND, response.status)
        self.assertEqual("this download does not exist", response_body_json["error"]["message"])

    async def test_stream_unsatisfiable(self) -> None:
        """
        Test if a graceful error is returned when the requested stream start is unsatisfiable.
        """
        download = self.create_mock_download()
        download.handle = Mock(is_valid=Mock(return_value=False))
        download.stream = Stream(download)
        download.stream.infohash = b"\x01" * 20
        download.stream.fileindex = 0
        download.stream.filesize = 0
        download.tdef = TorrentDef.load_from_memory(TORRENT_WITH_VIDEO)
        self.download_manager.get_download = Mock(return_value=download)

        request = StreamRequest({}, "01" * 20, 0, start=100, stop=200)
        with patch("tribler.core.libtorrent.download_manager.stream.Stream.enable", AsyncMock()):
            response = await self.endpoint.stream(request)
            await response.prepare(request)

        self.assertEqual(416, response.status)
        self.assertEqual("Requested Range Not Satisfiable", response.reason)

    async def test_stream(self) -> None:
        """
        Test if files can be streamed from a download.

        Note: we read the first byte of this test file (").
        """
        download = self.create_mock_download()
        download.handle = Mock(is_valid=Mock(return_value=False))
        download.stream = Stream(download)
        download.stream.close()
        download.stream.infohash = b"\x01" * 20
        download.stream.fileindex = 0
        download.stream.filesize = 1
        download.stream.filename = Path(__file__)
        download.stream.mapfile = Mock(return_value=Mock(piece=0))
        download.stream.firstpiece = 0
        download.stream.lastpiece = 0
        download.stream.prebuffsize = 0
        download.stream.enable = AsyncMock()
        download.lt_status = Mock(pieces=[True])
        download.tdef = TorrentDef.load_from_memory(TORRENT_WITH_VIDEO)
        self.download_manager.get_download = Mock(return_value=download)

        request = StreamRequest({}, "01" * 20, 0, start=0, stop=1)
        with patch("tribler.core.libtorrent.download_manager.stream.Stream.enable", AsyncMock()):
            response = await self.endpoint.stream(request)
            await response.prepare(request)

        self.assertEqual(206, response.status)
        self.assertEqual(b'"', request.get_transmitted())

    async def test_add_tracker(self) -> None:
        """
        Test if trackers can be added to a download.
        """
        trackers = ["http://127.0.0.1/somethingelse"]
        download = self.create_mock_download()
        download.handle = Mock(is_valid=Mock(return_value=True), trackers=Mock(return_value=trackers),
                               add_tracker=lambda tracker_dict: trackers.append(tracker_dict["url"]))
        self.download_manager.get_download = Mock(return_value=download)
        url = "http://127.0.0.1/announce"
        request = MockRequest(f"/api/downloads/{'01' * 20}/trackers", "PUT", {"url": url}, {"infohash": "01" * 20})

        response = await self.endpoint.add_tracker(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertTrue(response_body_json["added"])
        self.assertListEqual(["http://127.0.0.1/somethingelse", url], trackers)
        self.assertEqual(call(0, 1), download.handle.force_reannounce.call_args)

    async def test_add_tracker_no_download(self) -> None:
        """
        Test if adding a tracker fails when no download is found.
        """
        self.download_manager.get_download = Mock(return_value=None)
        request = MockRequest(f"/api/downloads/{'AA' * 20}/trackers", "PUT", {"url": "http://127.0.0.1/announce"},
                              {"infohash": "AA" * 20})

        response = await self.endpoint.add_tracker(request)

        self.assertEqual(404, response.status)

    async def test_add_tracker_no_url(self) -> None:
        """
        Test if adding a tracker fails when no tracker url is given.
        """
        download = self.create_mock_download()
        download.handle = Mock(is_valid=Mock(return_value=True), trackers=Mock(return_value=[]))
        self.download_manager.get_download = Mock(return_value=download)
        request = MockRequest(f"/api/downloads/{'AA' * 20}/trackers", "PUT", {"url": None}, {"infohash": "AA" * 20})

        response = await self.endpoint.add_tracker(request)

        self.assertEqual(400, response.status)

    async def test_add_tracker_handle_error(self) -> None:
        """
        Test if adding a tracker fails when a libtorrent internal error occurs.
        """
        trackers = ["http://127.0.0.1/somethingelse"]
        download = self.create_mock_download()
        download.handle = Mock(is_valid=Mock(return_value=True), trackers=Mock(return_value=trackers),
                               add_tracker=Mock(side_effect=RuntimeError("invalid torrent handle used")))
        self.download_manager.get_download = Mock(return_value=download)
        url = "http://127.0.0.1/announce"
        request = MockRequest(f"/api/downloads/{'01' * 20}/trackers", "PUT", {"url": url}, {"infohash": "01" * 20})

        response = await self.endpoint.add_tracker(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(500, response.status)
        self.assertEqual("invalid torrent handle used", response_body_json["error"]["message"])

    async def test_remove_tracker(self) -> None:
        """
        Test if trackers can be removed from a download.
        """
        trackers = [{"url": "http://127.0.0.1/somethingelse", "verified": True},
                    {"url": "http://127.0.0.1/announce", "verified": True}]
        download = self.create_mock_download()
        download.handle = Mock(is_valid=Mock(return_value=True), trackers=Mock(return_value=trackers),
                               replace_trackers=lambda new_trackers: (trackers.clear()
                                                                      is trackers.extend(new_trackers)))
        self.download_manager.get_download = Mock(return_value=download)
        url = "http://127.0.0.1/announce"
        request = MockRequest(f"/api/downloads/{'01' * 20}/trackers", "DELETE", {"url": url}, {"infohash": "01" * 20})

        response = await self.endpoint.remove_tracker(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertTrue(response_body_json["removed"])
        self.assertListEqual([{"url": "http://127.0.0.1/somethingelse", "verified": True}], trackers)

    async def test_remove_tracker_from_metainfo_announce(self) -> None:
        """
        Test if trackers can be removed from a download's metainfo with only b"announce".
        """
        download = self.create_mock_download()
        download.tdef = TorrentDef.load_from_memory(TORRENT_WITH_VIDEO)
        download.tdef.metainfo[b"announce"] = b"http://127.0.0.1/announce"
        download.handle = Mock(is_valid=Mock(return_value=True), trackers=Mock(return_value=[]))
        self.download_manager.get_download = Mock(return_value=download)
        url = "http://127.0.0.1/announce"
        request = MockRequest(f"/api/downloads/{'01' * 20}/trackers", "DELETE", {"url": url}, {"infohash": "01" * 20})

        response = await self.endpoint.remove_tracker(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertTrue(response_body_json["removed"])
        self.assertNotIn(b"announce", download.tdef.metainfo)

    async def test_remove_tracker_from_metainfo_announce_list(self) -> None:
        """
        Test if trackers can be removed from a download's metainfo with only b"announce-list".
        """
        download = self.create_mock_download()
        download.tdef = TorrentDef.load_from_memory(TORRENT_WITH_VIDEO)
        download.tdef.metainfo[b"announce-list"] = [[b"http://127.0.0.1/somethingelse"], [b"http://127.0.0.1/announce"]]
        download.handle = Mock(is_valid=Mock(return_value=True), trackers=Mock(return_value=[]))
        self.download_manager.get_download = Mock(return_value=download)
        url = "http://127.0.0.1/announce"
        request = MockRequest(f"/api/downloads/{'01' * 20}/trackers", "DELETE", {"url": url}, {"infohash": "01" * 20})

        response = await self.endpoint.remove_tracker(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertTrue(response_body_json["removed"])
        self.assertEqual(1, len(download.tdef.metainfo[b"announce-list"]))
        self.assertEqual(b"http://127.0.0.1/somethingelse", download.tdef.metainfo[b"announce-list"][0][0])

    async def test_remove_tracker_from_metainfo_announce_both_first(self) -> None:
        """
        Test if trackers can be removed from a download's metainfo where the b"announce" is first in b"announce-list".
        """
        download = self.create_mock_download()
        download.tdef = TorrentDef.load_from_memory(TORRENT_WITH_VIDEO)
        download.tdef.metainfo[b"announce"] = b"http://127.0.0.1/announce"
        download.tdef.metainfo[b"announce-list"] = [[b"http://127.0.0.1/announce"], [b"http://127.0.0.1/somethingelse"]]
        download.handle = Mock(is_valid=Mock(return_value=True), trackers=Mock(return_value=[]))
        self.download_manager.get_download = Mock(return_value=download)
        url = "http://127.0.0.1/announce"
        request = MockRequest(f"/api/downloads/{'01' * 20}/trackers", "DELETE", {"url": url}, {"infohash": "01" * 20})

        response = await self.endpoint.remove_tracker(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertTrue(response_body_json["removed"])
        self.assertEqual(1, len(download.tdef.metainfo[b"announce-list"]))
        self.assertEqual(b"http://127.0.0.1/somethingelse", download.tdef.metainfo[b"announce-list"][0][0])
        self.assertEqual(b"http://127.0.0.1/somethingelse", download.tdef.metainfo[b"announce"])

    async def test_remove_tracker_from_metainfo_announce_both_second(self) -> None:
        """
        Test if trackers can be removed from a download's metainfo where the b"announce" is second in b"announce-list".
        """
        download = self.create_mock_download()
        download.tdef = TorrentDef.load_from_memory(TORRENT_WITH_VIDEO)
        download.tdef.metainfo[b"announce"] = b"http://127.0.0.1/announce"
        download.tdef.metainfo[b"announce-list"] = [[b"http://127.0.0.1/somethingelse"], [b"http://127.0.0.1/announce"]]
        download.handle = Mock(is_valid=Mock(return_value=True), trackers=Mock(return_value=[]))
        self.download_manager.get_download = Mock(return_value=download)
        url = "http://127.0.0.1/announce"
        request = MockRequest(f"/api/downloads/{'01' * 20}/trackers", "DELETE", {"url": url}, {"infohash": "01" * 20})

        response = await self.endpoint.remove_tracker(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertTrue(response_body_json["removed"])
        self.assertEqual(1, len(download.tdef.metainfo[b"announce-list"]))
        self.assertEqual(b"http://127.0.0.1/somethingelse", download.tdef.metainfo[b"announce-list"][0][0])
        self.assertEqual(b"http://127.0.0.1/somethingelse", download.tdef.metainfo[b"announce"])

    async def test_remove_tracker_no_download(self) -> None:
        """
        Test if removing a tracker fails when no download is found.
        """
        self.download_manager.get_download = Mock(return_value=None)
        request = MockRequest(f"/api/downloads/{'AA' * 20}/trackers", "DELETE", {"url": "http://127.0.0.1/announce"},
                              {"infohash": "AA" * 20})

        response = await self.endpoint.remove_tracker(request)

        self.assertEqual(404, response.status)

    async def test_remove_tracker_no_url(self) -> None:
        """
        Test if removing a tracker fails when no tracker url is given.
        """
        download = self.create_mock_download()
        download.handle = Mock(is_valid=Mock(return_value=True), trackers=Mock(return_value=[]))
        self.download_manager.get_download = Mock(return_value=download)
        request = MockRequest(f"/api/downloads/{'AA' * 20}/trackers", "DELETE", {"url": None}, {"infohash": "AA" * 20})

        response = await self.endpoint.remove_tracker(request)

        self.assertEqual(400, response.status)

    async def test_remove_tracker_handle_error(self) -> None:
        """
        Test if removing a tracker fails when a libtorrent internal error occurs.
        """
        trackers = [{"url": "http://127.0.0.1/somethingelse", "verified": True},
                    {"url": "http://127.0.0.1/announce", "verified": True}]
        download = self.create_mock_download()
        download.handle = Mock(is_valid=Mock(return_value=True), trackers=Mock(return_value=trackers),
                               replace_trackers=Mock(side_effect=RuntimeError("invalid torrent handle used")))
        self.download_manager.get_download = Mock(return_value=download)
        url = "http://127.0.0.1/announce"
        request = MockRequest(f"/api/downloads/{'01' * 20}/trackers", "DELETE", {"url": url}, {"infohash": "01" * 20})

        response = await self.endpoint.remove_tracker(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(500, response.status)
        self.assertEqual("invalid torrent handle used", response_body_json["error"]["message"])

    async def test_tracker_force_announce(self) -> None:
        """
        Test if trackers can be force announced.
        """
        trackers = [{"url": "http://127.0.0.1/somethingelse", "verified": True},
                    {"url": "http://127.0.0.1/announce", "verified": True}]
        download = self.create_mock_download()
        download.handle = Mock(is_valid=Mock(return_value=True), trackers=Mock(return_value=trackers))
        self.download_manager.get_download = Mock(return_value=download)
        url = "http://127.0.0.1/announce"
        request = MockRequest(f"/api/downloads/{'01' * 20}/tracker_force_announce", "PUT", {"url": url},
                              {"infohash": "01" * 20})

        response = await self.endpoint.tracker_force_announce(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertTrue(response_body_json["forced"])
        self.assertEqual(call(0, 1), download.handle.force_reannounce.call_args)

    async def test_tracker_force_announce_no_download(self) -> None:
        """
        Test if force-announcing a tracker fails when no download is found.
        """
        self.download_manager.get_download = Mock(return_value=None)
        request = MockRequest(f"/api/downloads/{'AA' * 20}/tracker_force_announce", "PUT",
                              {"url": "http://127.0.0.1/announce"}, {"infohash": "AA" * 20})

        response = await self.endpoint.tracker_force_announce(request)

        self.assertEqual(404, response.status)

    async def test_tracker_force_announce_no_url(self) -> None:
        """
        Test if force-announcing a tracker fails when no tracker url is given.
        """
        download = self.create_mock_download()
        download.handle = Mock(is_valid=Mock(return_value=True), trackers=Mock(return_value=[]))
        self.download_manager.get_download = Mock(return_value=download)
        request = MockRequest(f"/api/downloads/{'AA' * 20}/tracker_force_announce", "PUT", {"url": None},
                              {"infohash": "AA" * 20})

        response = await self.endpoint.tracker_force_announce(request)

        self.assertEqual(400, response.status)

    async def test_tracker_force_announce_handle_error(self) -> None:
        """
        Test if force-announcing a tracker fails when a libtorrent internal error occurs.
        """
        trackers = [{"url": "http://127.0.0.1/somethingelse", "verified": True},
                    {"url": "http://127.0.0.1/announce", "verified": True}]
        download = self.create_mock_download()
        download.handle = Mock(is_valid=Mock(return_value=True), trackers=Mock(return_value=trackers),
                               force_reannounce=Mock(side_effect=RuntimeError("invalid torrent handle used")))
        self.download_manager.get_download = Mock(return_value=download)
        url = "http://127.0.0.1/announce"
        request = MockRequest(f"/api/downloads/{'01' * 20}/tracker_force_announce", "PUT", {"url": url},
                              {"infohash": "01" * 20})

        response = await self.endpoint.tracker_force_announce(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(500, response.status)
        self.assertEqual("invalid torrent handle used", response_body_json["error"]["message"])
