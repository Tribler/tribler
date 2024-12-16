import base64
from io import StringIO
from pathlib import Path
from unittest.mock import AsyncMock, Mock, patch

from configobj import ConfigObj
from ipv8.test.base import TestBase
from ipv8.test.REST.rest_base import MockRequest, response_to_json

import tribler.core.libtorrent.restapi.create_torrent_endpoint as ep_module
from tribler.core.libtorrent.download_manager.download_config import SPEC_CONTENT, DownloadConfig
from tribler.core.libtorrent.restapi.create_torrent_endpoint import CreateTorrentEndpoint
from tribler.core.restapi.rest_endpoint import HTTP_BAD_REQUEST, HTTP_INTERNAL_SERVER_ERROR
from tribler.test_unit.core.libtorrent.mocks import TORRENT_WITH_DIRS_CONTENT
from tribler.test_unit.mocks import MockTriblerConfigManager


class TestCreateTorrentEndpoint(TestBase):
    """
    Tests for the CreateTorrentEndpoint class.
    """

    def setUp(self) -> None:
        """
        Create a mocked DownloadManager and a CreateTorrentEndpoint.
        """
        super().setUp()

        self.download_manager = Mock()
        self.endpoint = CreateTorrentEndpoint(self.download_manager)

    async def test_no_files(self) -> None:
        """
        Test if a request without files leads to a bad request status.
        """
        request = MockRequest("/api/createtorrent", "POST", {})

        response = await self.endpoint.create_torrent(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_BAD_REQUEST, response.status)
        self.assertEqual("files parameter missing", response_body_json["error"]["message"])

    async def test_failure_oserror(self) -> None:
        """
        Test if processing a request that leads to an OSError is gracefully reported.
        """
        request = MockRequest("/api/createtorrent", "POST", {"files": [str(Path(__file__))]})

        with patch.dict(ep_module.__dict__, {"create_torrent_file": Mock(side_effect=OSError("test"))}):
            response = await self.endpoint.create_torrent(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_INTERNAL_SERVER_ERROR, response.status)
        self.assertTrue(response_body_json["error"]["handled"])
        self.assertEqual("OSError: test", response_body_json["error"]["message"])

    async def test_failure_unicodedecodeerror(self) -> None:
        """
        Test if processing a request that leads to an OSError is gracefully reported.
        """
        request = MockRequest("/api/createtorrent", "POST", {"files": [str(Path(__file__))]})

        with patch.dict(ep_module.__dict__, {"create_torrent_file":
                                             Mock(side_effect=UnicodeDecodeError("utf-8", b"", 0, 1, "𓀬"))}):
            response = await self.endpoint.create_torrent(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_INTERNAL_SERVER_ERROR, response.status)
        self.assertTrue(response_body_json["error"]["handled"])
        self.assertEqual("UnicodeDecodeError: 'utf-8' codec can't decode bytes in position 0-0: 𓀬",
                         response_body_json["error"]["message"])

    async def test_failure_runtimeerror(self) -> None:
        """
        Test if processing a request that leads to an RuntimeError is gracefully reported.
        """
        request = MockRequest("/api/createtorrent", "POST", {"files": [str(Path(__file__))]})

        with patch.dict(ep_module.__dict__, {"create_torrent_file": Mock(side_effect=RuntimeError("test"))}):
            response = await self.endpoint.create_torrent(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_INTERNAL_SERVER_ERROR, response.status)
        self.assertTrue(response_body_json["error"]["handled"])
        self.assertEqual("RuntimeError: test", response_body_json["error"]["message"])

    async def test_create_default(self) -> None:
        """
        Test if creating a torrent from defaults works.
        """
        request = MockRequest("/api/createtorrent", "POST", {"files": [str(Path(__file__))]})
        mocked_create_torrent_file = Mock(return_value={"metainfo": TORRENT_WITH_DIRS_CONTENT})

        with patch.dict(ep_module.__dict__, {"create_torrent_file": mocked_create_torrent_file}):
            response = await self.endpoint.create_torrent(request)
        response_body_json = await response_to_json(response)

        _, call_params, __ = mocked_create_torrent_file.call_args.args

        self.assertEqual(200, response.status)
        self.assertEqual(TORRENT_WITH_DIRS_CONTENT, base64.b64decode(response_body_json["torrent"]))
        self.assertFalse(call_params[b"nodes"])
        self.assertFalse(call_params[b"httpseeds"])
        self.assertFalse(call_params[b"encoding"])
        self.assertEqual(0, call_params[b"piece length"])

    async def test_create_with_comment(self) -> None:
        """
        Test if creating a torrent with a custom comment works.
        """
        request = MockRequest("/api/createtorrent", "POST", {"files": [str(Path(__file__))], "description": "test"})
        mocked_create_torrent_file = Mock(return_value={"metainfo": TORRENT_WITH_DIRS_CONTENT})

        with patch.dict(ep_module.__dict__, {"create_torrent_file": mocked_create_torrent_file}):
            response = await self.endpoint.create_torrent(request)
        response_body_json = await response_to_json(response)

        _, call_params, __ = mocked_create_torrent_file.call_args.args

        self.assertEqual(200, response.status)
        self.assertEqual(TORRENT_WITH_DIRS_CONTENT, base64.b64decode(response_body_json["torrent"]))
        self.assertEqual(b"test", call_params[b"comment"])

    async def test_create_with_trackers(self) -> None:
        """
        Test if creating a torrent with custom trackers works.
        """
        request = MockRequest("/api/createtorrent", "POST",{
            "files": [str(Path(__file__))],
            "trackers": ["http://127.0.0.1/announce", "http://10.0.0.2/announce"]
        })
        mocked_create_torrent_file = Mock(return_value={"metainfo": TORRENT_WITH_DIRS_CONTENT})

        with patch.dict(ep_module.__dict__, {"create_torrent_file": mocked_create_torrent_file}):
            response = await self.endpoint.create_torrent(request)
        response_body_json = await response_to_json(response)

        _, call_params, __ = mocked_create_torrent_file.call_args.args

        self.assertEqual(200, response.status)
        self.assertEqual(TORRENT_WITH_DIRS_CONTENT, base64.b64decode(response_body_json["torrent"]))
        self.assertEqual(b"http://127.0.0.1/announce", call_params[b"announce"])
        self.assertEqual([b"http://127.0.0.1/announce", b"http://10.0.0.2/announce"], call_params[b"announce-list"])

    async def test_create_with_name(self) -> None:
        """
        Test if creating a torrent with a custom name works.
        """
        request = MockRequest("/api/createtorrent", "POST", {"files": [str(Path(__file__))], "name": "test"})
        mocked_create_torrent_file = Mock(return_value={"metainfo": TORRENT_WITH_DIRS_CONTENT})

        with patch.dict(ep_module.__dict__, {"create_torrent_file": mocked_create_torrent_file}):
            response = await self.endpoint.create_torrent(request)
        response_body_json = await response_to_json(response)

        _, call_params, __ = mocked_create_torrent_file.call_args.args

        self.assertEqual(200, response.status)
        self.assertEqual(TORRENT_WITH_DIRS_CONTENT, base64.b64decode(response_body_json["torrent"]))
        self.assertEqual(b"test", call_params[b"name"])

    async def test_create_and_start(self) -> None:
        """
        Test if creating and starting a download works if download is set to 1.
        """
        self.download_manager.config = MockTriblerConfigManager()
        self.download_manager.start_download = AsyncMock()
        request = MockRequest("/api/createtorrent", "POST", {"files": [str(Path(__file__))], "download": "1"})
        mocked_create = Mock(return_value={"metainfo": TORRENT_WITH_DIRS_CONTENT,
                                           "base_dir": str(Path(__file__).parent)})

        with patch("tribler.core.libtorrent.download_manager.download_config.DownloadConfig.from_defaults",
                   lambda _: DownloadConfig(ConfigObj(StringIO(SPEC_CONTENT)))), patch.dict(ep_module.__dict__,
                                                                                            {"create_torrent_file":
                                                                                                 mocked_create}):
            response = await self.endpoint.create_torrent(request)
        response_body_json = await response_to_json(response)

        _, tdef, __ = self.download_manager.start_download.call_args.args

        self.assertEqual(200, response.status)
        self.assertEqual(TORRENT_WITH_DIRS_CONTENT, base64.b64decode(response_body_json["torrent"]))
        self.assertEqual(b"\xb3\xba\x19\xc93\xda\x95\x84k\xfd\xf7Z\xd0\x8a\x94\x9cl\xea\xc7\xbc",
                         tdef.infohash)
