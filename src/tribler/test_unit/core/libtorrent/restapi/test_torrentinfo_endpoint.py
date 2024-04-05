import json
from asyncio import TimeoutError
from binascii import unhexlify
from ssl import SSLError
from unittest.mock import AsyncMock, Mock, patch

from aiohttp import ClientConnectorError, ClientResponseError, ServerConnectionError
from ipv8.test.base import TestBase

import tribler
from tribler.core.libtorrent.restapi.torrentinfo_endpoint import TorrentInfoEndpoint, recursive_unicode
from tribler.core.libtorrent.torrentdef import TorrentDef, TorrentDefNoMetainfo
from tribler.core.restapi.rest_endpoint import HTTP_BAD_REQUEST, HTTP_INTERNAL_SERVER_ERROR
from tribler.test_unit.base_restapi import MockRequest, response_to_json
from tribler.test_unit.core.libtorrent.mocks import TORRENT_WITH_DIRS_CONTENT


class GetTorrentInfoRequest(MockRequest):
    """
    A MockRequest that mimics GetTorrentInfoRequests.
    """

    def __init__(self, query: dict) -> None:
        """
        Create a new GetTorrentInfoRequest.
        """
        super().__init__(query, "GET", "/torrentinfo")


async def mock_unshorten(uri: str) -> str:
    """
    Don't following links.
    """
    return uri


class TestTorrentInfoEndpoint(TestBase):
    """
    Tests for the TorrentInfoEndpoint class.
    """

    def setUp(self) -> None:
        """
        Create a mocked DownloadManager and a TorrentInfoEndpoint.
        """
        super().setUp()

        self.download_manager = Mock()
        self.endpoint = TorrentInfoEndpoint(self.download_manager)

    async def test_get_torrent_info_bad_hops(self) -> None:
        """
        Test if a graceful error is returned when the supplied number of hops is an int value.
        """
        response = await self.endpoint.get_torrent_info(GetTorrentInfoRequest({"hops": "foo", "uri": "file://"}))
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_BAD_REQUEST, response.status)
        self.assertEqual("wrong value of 'hops' parameter: foo", response_body_json["error"])

    async def test_get_torrent_info_bad_scheme(self) -> None:
        """
        Test if a graceful error is returned when the supplied the URI scheme is unknown.
        """
        response = await self.endpoint.get_torrent_info(GetTorrentInfoRequest({"hops": 0, "uri": "xxx://"}))
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_BAD_REQUEST, response.status)
        self.assertEqual("invalid uri", response_body_json["error"])

    async def test_get_torrent_info_no_metainfo(self) -> None:
        """
        Test if a graceful error is returned when no metainfo is available for a file.
        """
        tdef = TorrentDefNoMetainfo(b"\x01" * 20, b"test")
        with patch("tribler.core.libtorrent.torrentdef.TorrentDef.load", AsyncMock(return_value=tdef)):
            response = await self.endpoint.get_torrent_info(GetTorrentInfoRequest({"hops": 0, "uri": "file://"}))
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_INTERNAL_SERVER_ERROR, response.status)
        self.assertEqual("metainfo error", response_body_json["error"])

    async def test_get_torrent_info_file_filenotfounderror(self) -> None:
        """
        Test if a graceful error is returned when a FileNotFoundError occurs when loading a torrent.
        """
        with patch("tribler.core.libtorrent.torrentdef.TorrentDef.load", AsyncMock(side_effect=FileNotFoundError)):
            response = await self.endpoint.get_torrent_info(GetTorrentInfoRequest({"hops": 0, "uri": "file://"}))
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_INTERNAL_SERVER_ERROR, response.status)
        self.assertEqual("error while decoding torrent file: .", response_body_json["error"])

    async def test_get_torrent_info_file_typeerror(self) -> None:
        """
        Test if a graceful error is returned when a TypeError occurs when loading a torrent.
        """
        with patch("tribler.core.libtorrent.torrentdef.TorrentDef.load", AsyncMock(side_effect=TypeError)):
            response = await self.endpoint.get_torrent_info(GetTorrentInfoRequest({"hops": 0, "uri": "file://"}))
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_INTERNAL_SERVER_ERROR, response.status)
        self.assertEqual("error while decoding torrent file: .", response_body_json["error"])

    async def test_get_torrent_info_file_valueerror(self) -> None:
        """
        Test if a graceful error is returned when a ValueError occurs when loading a torrent.
        """
        with patch("tribler.core.libtorrent.torrentdef.TorrentDef.load", AsyncMock(side_effect=ValueError)):
            response = await self.endpoint.get_torrent_info(GetTorrentInfoRequest({"hops": 0, "uri": "file://"}))
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_INTERNAL_SERVER_ERROR, response.status)
        self.assertEqual("error while decoding torrent file: .", response_body_json["error"])

    async def test_get_torrent_info_file_runtimeerror(self) -> None:
        """
        Test if a graceful error is returned when a RuntimeError occurs when loading a torrent.
        """
        with patch("tribler.core.libtorrent.torrentdef.TorrentDef.load", AsyncMock(side_effect=RuntimeError)):
            response = await self.endpoint.get_torrent_info(GetTorrentInfoRequest({"hops": 0, "uri": "file://"}))
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_INTERNAL_SERVER_ERROR, response.status)
        self.assertEqual("error while decoding torrent file: .", response_body_json["error"])

    async def test_get_torrent_info_magnet_runtimeerror_compat(self) -> None:
        """
        Test if a graceful error is returned when a RuntimeError occurs when loading a magnet in compatibility mode.
        """
        with patch.dict(tribler.core.libtorrent.restapi.torrentinfo_endpoint.__dict__,
                        {"lt": Mock(parse_magnet_uri=Mock(side_effect=RuntimeError))}):
            response = await self.endpoint.get_torrent_info(GetTorrentInfoRequest({"hops": 0, "uri": "magnet://"}))
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_BAD_REQUEST, response.status)
        self.assertEqual("Error while getting an infohash from magnet: RuntimeError: ", response_body_json["error"])

    async def test_get_torrent_info_magnet_runtimeerror_modern(self) -> None:
        """
        Test if a graceful error is returned when a RuntimeError occurs when loading a magnet.
        """
        with patch.dict(tribler.core.libtorrent.restapi.torrentinfo_endpoint.__dict__,
                        {"lt": Mock(parse_magnet_uri=type("test", (object, ), {
                            "info_hash": property(Mock(side_effect=RuntimeError)),
                            "__init__": lambda _, __: None
                        }))}):
            response = await self.endpoint.get_torrent_info(GetTorrentInfoRequest({"hops": 0, "uri": "magnet://"}))
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_BAD_REQUEST, response.status)
        self.assertEqual("Error while getting an infohash from magnet: RuntimeError: ", response_body_json["error"])

    async def test_get_torrent_info_magnet_no_metainfo(self) -> None:
        """
        Test if a graceful error is returned when no metainfo is available for a magnet.
        """
        self.download_manager.get_metainfo = AsyncMock(return_value=None)

        with patch.dict(tribler.core.libtorrent.restapi.torrentinfo_endpoint.__dict__,
                        {"lt": Mock(parse_magnet_uri=Mock(return_value={"info_hash": b"\x01" * 20}))}):
            response = await self.endpoint.get_torrent_info(GetTorrentInfoRequest({"hops": 0, "uri": "magnet://"}))
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_INTERNAL_SERVER_ERROR, response.status)
        self.assertEqual("metainfo error", response_body_json["error"])
        self.assertEqual(b"\x01" * 20, self.download_manager.get_metainfo.call_args.args[0])
        self.assertEqual(10, self.download_manager.get_metainfo.call_args.kwargs["timeout"])
        self.assertEqual(0, self.download_manager.get_metainfo.call_args.kwargs["hops"])
        self.assertEqual("magnet://", self.download_manager.get_metainfo.call_args.kwargs["url"])

    async def test_get_torrent_info_http_serverconnectionerror(self) -> None:
        """
        Test if a graceful error is returned when a ServerConnectionError occurs when loading from an HTTP link.
        """
        with patch.dict(tribler.core.libtorrent.restapi.torrentinfo_endpoint.__dict__,
                        {"unshorten": mock_unshorten}), \
                patch("tribler.core.libtorrent.restapi.torrentinfo_endpoint.query_uri",
                      AsyncMock(side_effect=ServerConnectionError("test"))):
            response = await self.endpoint.get_torrent_info(GetTorrentInfoRequest({"hops": 0,
                                                                                   "uri": "http://127.0.0.1/file"}))
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_INTERNAL_SERVER_ERROR, response.status)
        self.assertEqual("test", response_body_json["error"])

    async def test_get_torrent_info_http_clientresponseerror(self) -> None:
        """
        Test if a graceful error is returned when a ClientResponseError occurs when loading from an HTTP link.
        """
        with patch.dict(tribler.core.libtorrent.restapi.torrentinfo_endpoint.__dict__,
                        {"unshorten": mock_unshorten}), \
                patch("tribler.core.libtorrent.restapi.torrentinfo_endpoint.query_uri",
                      AsyncMock(side_effect=ClientResponseError(Mock(real_url="test"), ()))):
            response = await self.endpoint.get_torrent_info(GetTorrentInfoRequest({"hops": 0,
                                                                                   "uri": "http://127.0.0.1/file"}))
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_INTERNAL_SERVER_ERROR, response.status)
        self.assertEqual("0, message='', url='test'", response_body_json["error"])

    async def test_get_torrent_info_http_sslerror(self) -> None:
        """
        Test if a graceful error is returned when a SSLError occurs when loading from an HTTP link.
        """
        with patch.dict(tribler.core.libtorrent.restapi.torrentinfo_endpoint.__dict__,
                        {"unshorten": mock_unshorten}), \
                patch("tribler.core.libtorrent.restapi.torrentinfo_endpoint.query_uri",
                      AsyncMock(side_effect=SSLError("test"))):
            response = await self.endpoint.get_torrent_info(GetTorrentInfoRequest({"hops": 0,
                                                                                   "uri": "http://127.0.0.1/file"}))
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_INTERNAL_SERVER_ERROR, response.status)
        self.assertEqual("('test',)", response_body_json["error"])

    async def test_get_torrent_info_http_clientconnectorerror(self) -> None:
        """
        Test if a graceful error is returned when a ClientConnectorError occurs when loading from an HTTP link.
        """
        with patch.dict(tribler.core.libtorrent.restapi.torrentinfo_endpoint.__dict__,
                        {"unshorten": mock_unshorten}), \
                patch("tribler.core.libtorrent.restapi.torrentinfo_endpoint.query_uri",
                      AsyncMock(side_effect=ClientConnectorError(Mock(ssl="default", host="test", port=42),
                                                                 OSError("test")))):
            response = await self.endpoint.get_torrent_info(GetTorrentInfoRequest({"hops": 0,
                                                                                   "uri": "http://127.0.0.1/file"}))
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_INTERNAL_SERVER_ERROR, response.status)
        self.assertEqual("Cannot connect to host test:42 ssl:default [None]", response_body_json["error"])

    async def test_get_torrent_info_http_timeouterror(self) -> None:
        """
        Test if a graceful error is returned when a TimeoutError occurs when loading from an HTTP link.
        """
        with patch.dict(tribler.core.libtorrent.restapi.torrentinfo_endpoint.__dict__,
                        {"unshorten": mock_unshorten}), \
                patch("tribler.core.libtorrent.restapi.torrentinfo_endpoint.query_uri",
                      AsyncMock(side_effect=TimeoutError("test"))):
            response = await self.endpoint.get_torrent_info(GetTorrentInfoRequest({"hops": 0,
                                                                                   "uri": "http://127.0.0.1/file"}))
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_INTERNAL_SERVER_ERROR, response.status)
        self.assertEqual("test", response_body_json["error"])

    async def test_get_torrent_info_http_valueerror(self) -> None:
        """
        Test if a graceful error is returned when a ValueError occurs when loading from an HTTP link.
        """
        with patch.dict(tribler.core.libtorrent.restapi.torrentinfo_endpoint.__dict__,
                        {"unshorten": mock_unshorten}), \
                patch("tribler.core.libtorrent.restapi.torrentinfo_endpoint.query_uri",
                      AsyncMock(side_effect=ValueError("test"))):
            response = await self.endpoint.get_torrent_info(GetTorrentInfoRequest({"hops": 0,
                                                                                   "uri": "http://127.0.0.1/file"}))
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_INTERNAL_SERVER_ERROR, response.status)
        self.assertEqual("test", response_body_json["error"])

    async def test_get_torrent_info_https_serverconnectionerror(self) -> None:
        """
        Test if a graceful error is returned when a ServerConnectionError occurs when loading from an HTTPS link.
        """
        with patch.dict(tribler.core.libtorrent.restapi.torrentinfo_endpoint.__dict__,
                        {"unshorten": mock_unshorten}), \
                patch("tribler.core.libtorrent.restapi.torrentinfo_endpoint.query_uri",
                      AsyncMock(side_effect=ServerConnectionError("test"))):
            response = await self.endpoint.get_torrent_info(GetTorrentInfoRequest({"hops": 0,
                                                                                   "uri": "https://127.0.0.1/file"}))
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_INTERNAL_SERVER_ERROR, response.status)
        self.assertEqual("test", response_body_json["error"])

    async def test_get_torrent_info_https_clientresponseerror(self) -> None:
        """
        Test if a graceful error is returned when a ClientResponseError occurs when loading from an HTTPS link.
        """
        with patch.dict(tribler.core.libtorrent.restapi.torrentinfo_endpoint.__dict__,
                        {"unshorten": mock_unshorten}), \
                patch("tribler.core.libtorrent.restapi.torrentinfo_endpoint.query_uri",
                      AsyncMock(side_effect=ClientResponseError(Mock(real_url="test"), ()))):
            response = await self.endpoint.get_torrent_info(GetTorrentInfoRequest({"hops": 0,
                                                                                   "uri": "https://127.0.0.1/file"}))
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_INTERNAL_SERVER_ERROR, response.status)
        self.assertEqual("0, message='', url='test'", response_body_json["error"])

    async def test_get_torrent_info_https_sslerror(self) -> None:
        """
        Test if a graceful error is returned when a SSLError occurs when loading from an HTTPS link.
        """
        with patch.dict(tribler.core.libtorrent.restapi.torrentinfo_endpoint.__dict__,
                        {"unshorten": mock_unshorten}), \
                patch("tribler.core.libtorrent.restapi.torrentinfo_endpoint.query_uri",
                      AsyncMock(side_effect=SSLError("test"))):
            response = await self.endpoint.get_torrent_info(GetTorrentInfoRequest({"hops": 0,
                                                                                   "uri": "https://127.0.0.1/file"}))
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_INTERNAL_SERVER_ERROR, response.status)
        self.assertEqual("('test',)", response_body_json["error"])

    async def test_get_torrent_info_https_clientconnectorerror(self) -> None:
        """
        Test if a graceful error is returned when a ClientConnectorError occurs when loading from an HTTPS link.
        """
        with patch.dict(tribler.core.libtorrent.restapi.torrentinfo_endpoint.__dict__,
                        {"unshorten": mock_unshorten}), \
                patch("tribler.core.libtorrent.restapi.torrentinfo_endpoint.query_uri",
                      AsyncMock(side_effect=ClientConnectorError(Mock(ssl="default", host="test", port=42),
                                                                 OSError("test")))):
            response = await self.endpoint.get_torrent_info(GetTorrentInfoRequest({"hops": 0,
                                                                                   "uri": "https://127.0.0.1/file"}))
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_INTERNAL_SERVER_ERROR, response.status)
        self.assertEqual("Cannot connect to host test:42 ssl:default [None]", response_body_json["error"])

    async def test_get_torrent_info_https_timeouterror(self) -> None:
        """
        Test if a graceful error is returned when a TimeoutError occurs when loading from an HTTPS link.
        """
        with patch.dict(tribler.core.libtorrent.restapi.torrentinfo_endpoint.__dict__,
                        {"unshorten": mock_unshorten}), \
                patch("tribler.core.libtorrent.restapi.torrentinfo_endpoint.query_uri",
                      AsyncMock(side_effect=TimeoutError("test"))):
            response = await self.endpoint.get_torrent_info(GetTorrentInfoRequest({"hops": 0,
                                                                                   "uri": "https://127.0.0.1/file"}))
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_INTERNAL_SERVER_ERROR, response.status)
        self.assertEqual("test", response_body_json["error"])

    async def test_get_torrent_info_https_valueerror(self) -> None:
        """
        Test if a graceful error is returned when a ValueError occurs when loading from an HTTPS link.
        """
        with patch.dict(tribler.core.libtorrent.restapi.torrentinfo_endpoint.__dict__,
                        {"unshorten": mock_unshorten}), \
                patch("tribler.core.libtorrent.restapi.torrentinfo_endpoint.query_uri",
                      AsyncMock(side_effect=ValueError("test"))):
            response = await self.endpoint.get_torrent_info(GetTorrentInfoRequest({"hops": 0,
                                                                                   "uri": "https://127.0.0.1/file"}))
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_INTERNAL_SERVER_ERROR, response.status)
        self.assertEqual("test", response_body_json["error"])

    async def test_get_torrent_info_http_no_metainfo(self) -> None:
        """
        Test if a graceful error is returned when no metainfo is available for a http link.
        """
        self.download_manager.get_metainfo = AsyncMock(return_value=None)

        with patch.dict(tribler.core.libtorrent.restapi.torrentinfo_endpoint.__dict__, {"unshorten": mock_unshorten}), \
                patch("tribler.core.libtorrent.restapi.torrentinfo_endpoint.query_uri",
                      AsyncMock(return_value=b"de")):
            response = await self.endpoint.get_torrent_info(GetTorrentInfoRequest({"hops": 0,
                                                                                   "uri": "http://127.0.0.1/file"}))
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_INTERNAL_SERVER_ERROR, response.status)
        self.assertEqual("metainfo error", response_body_json["error"])

    async def test_get_torrent_info_https_no_metainfo(self) -> None:
        """
        Test if a graceful error is returned when no metainfo is available for a https link.
        """
        self.download_manager.get_metainfo = AsyncMock(return_value=None)

        with patch.dict(tribler.core.libtorrent.restapi.torrentinfo_endpoint.__dict__, {"unshorten": mock_unshorten}), \
                patch("tribler.core.libtorrent.restapi.torrentinfo_endpoint.query_uri",
                      AsyncMock(return_value=b"de")):
            response = await self.endpoint.get_torrent_info(GetTorrentInfoRequest({"hops": 0,
                                                                                   "uri": "https://127.0.0.1/file"}))
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_INTERNAL_SERVER_ERROR, response.status)
        self.assertEqual("metainfo error", response_body_json["error"])

    async def test_get_torrent_info_http_redirect_magnet_no_metainfo(self) -> None:
        """
        Test if a graceful error is returned when no metainfo is available for a magnet returned by a HTTP link.
        """
        self.download_manager.get_metainfo = AsyncMock(return_value=None)

        with patch.dict(tribler.core.libtorrent.restapi.torrentinfo_endpoint.__dict__,
                        {"unshorten": mock_unshorten}), \
                patch("tribler.core.libtorrent.restapi.torrentinfo_endpoint.query_uri",
                      AsyncMock(return_value=b"magnet://")), \
                patch.dict(tribler.core.libtorrent.restapi.torrentinfo_endpoint.__dict__,
                           {"lt": Mock(parse_magnet_uri=Mock(return_value={"info_hash": b"\x01" * 20}))}):
            response = await self.endpoint.get_torrent_info(GetTorrentInfoRequest({"hops": 0,
                                                                                   "uri": "http://127.0.0.1/file"}))
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_INTERNAL_SERVER_ERROR, response.status)
        self.assertEqual("metainfo error", response_body_json["error"])
        self.assertEqual(b"\x01" * 20, self.download_manager.get_metainfo.call_args.args[0])
        self.assertEqual(10.0, self.download_manager.get_metainfo.call_args.kwargs["timeout"])
        self.assertEqual(0, self.download_manager.get_metainfo.call_args.kwargs["hops"])
        self.assertEqual("magnet://", self.download_manager.get_metainfo.call_args.kwargs["url"])

    async def test_get_torrent_info_https_redirect_magnet_no_metainfo(self) -> None:
        """
        Test if a graceful error is returned when no metainfo is available for a magnet returned by a HTTPS link.
        """
        self.download_manager.get_metainfo = AsyncMock(return_value=None)

        with patch.dict(tribler.core.libtorrent.restapi.torrentinfo_endpoint.__dict__,
                        {"unshorten": mock_unshorten}), \
                patch("tribler.core.libtorrent.restapi.torrentinfo_endpoint.query_uri",
                      AsyncMock(return_value=b"magnet://")), \
                patch.dict(tribler.core.libtorrent.restapi.torrentinfo_endpoint.__dict__,
                           {"lt": Mock(parse_magnet_uri=Mock(return_value={"info_hash": b"\x01" * 20}))}):
            response = await self.endpoint.get_torrent_info(GetTorrentInfoRequest({"hops": 0,
                                                                                   "uri": "https://127.0.0.1/file"}))
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_INTERNAL_SERVER_ERROR, response.status)
        self.assertEqual("metainfo error", response_body_json["error"])
        self.assertEqual(b"\x01" * 20, self.download_manager.get_metainfo.call_args.args[0])
        self.assertEqual(10.0, self.download_manager.get_metainfo.call_args.kwargs["timeout"])
        self.assertEqual(0, self.download_manager.get_metainfo.call_args.kwargs["hops"])
        self.assertEqual("magnet://", self.download_manager.get_metainfo.call_args.kwargs["url"])

    async def test_get_torrent_info_invalid_response_empty_metainfo(self) -> None:
        """
        Test if a graceful error is returned when the metainfo is empty for a file.
        """
        tdef = TorrentDef().load_from_memory(TORRENT_WITH_DIRS_CONTENT)
        tdef.metainfo = 3
        with patch("tribler.core.libtorrent.torrentdef.TorrentDef.load", AsyncMock(return_value=tdef)):
            response = await self.endpoint.get_torrent_info(GetTorrentInfoRequest({"hops": 0, "uri": "file://"}))
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_INTERNAL_SERVER_ERROR, response.status)
        self.assertEqual("invalid response", response_body_json["error"])

    async def test_get_torrent_info_invalid_response_empty_info(self) -> None:
        """
        Test if a graceful error is returned when the metainfo is empty for a file.
        """
        tdef = TorrentDef().load_from_memory(TORRENT_WITH_DIRS_CONTENT)
        tdef.metainfo.pop(b"info")
        with patch("tribler.core.libtorrent.torrentdef.TorrentDef.load", AsyncMock(return_value=tdef)):
            response = await self.endpoint.get_torrent_info(GetTorrentInfoRequest({"hops": 0, "uri": "file://"}))
        response_body_json = await response_to_json(response)

        self.assertEqual(HTTP_INTERNAL_SERVER_ERROR, response.status)
        self.assertEqual("invalid response", response_body_json["error"])

    async def test_get_torrent_info_valid_download(self) -> None:
        """
        Test if a valid download has its info returned correctly.
        """
        tdef = TorrentDef().load_from_memory(TORRENT_WITH_DIRS_CONTENT)
        self.download_manager.metainfo_requests = {}
        with patch("tribler.core.libtorrent.torrentdef.TorrentDef.load", AsyncMock(return_value=tdef)):
            response = await self.endpoint.get_torrent_info(GetTorrentInfoRequest({"hops": 0, "uri": "file://"}))
        response_body_json = await response_to_json(response)
        response_info_json = json.loads(unhexlify(response_body_json["metainfo"]))

        self.assertEqual(200, response.status)
        self.assertTrue(response_body_json["download_exists"])
        self.assertEqual(tdef.metainfo[b"comment"].decode(), response_info_json["comment"])
        self.assertEqual(tdef.metainfo[b"created by"].decode(), response_info_json["created by"])
        self.assertEqual(tdef.metainfo[b"creation date"], response_info_json["creation date"])
        self.assertEqual(tdef.metainfo[b"info"][b"name"].decode(), response_info_json["info"]["name"])
        self.assertEqual(tdef.metainfo[b"info"][b"piece length"], response_info_json["info"]["piece length"])

    async def test_get_torrent_info_valid_metainfo_request(self) -> None:
        """
        Test if a valid metainfo request has its info returned correctly.
        """
        tdef = TorrentDef().load_from_memory(TORRENT_WITH_DIRS_CONTENT)
        self.download_manager.metainfo_requests = {tdef.infohash: [self.download_manager.downloads.get(tdef.infohash)]}
        with patch("tribler.core.libtorrent.torrentdef.TorrentDef.load", AsyncMock(return_value=tdef)):
            response = await self.endpoint.get_torrent_info(GetTorrentInfoRequest({"hops": 0, "uri": "file://"}))
        response_body_json = await response_to_json(response)
        response_info_json = json.loads(unhexlify(response_body_json["metainfo"]))

        self.assertEqual(200, response.status)
        self.assertFalse(response_body_json["download_exists"])
        self.assertEqual(tdef.metainfo[b"comment"].decode(), response_info_json["comment"])
        self.assertEqual(tdef.metainfo[b"created by"].decode(), response_info_json["created by"])
        self.assertEqual(tdef.metainfo[b"creation date"], response_info_json["creation date"])
        self.assertEqual(tdef.metainfo[b"info"][b"name"].decode(), response_info_json["info"]["name"])
        self.assertEqual(tdef.metainfo[b"info"][b"piece length"], response_info_json["info"]["piece length"])

    def test_recursive_unicode_empty(self) -> None:
        """
        Test if empty items can be recursively converted to unicode.
        """
        self.assertEqual({}, recursive_unicode({}))
        self.assertEqual([], recursive_unicode([]))
        self.assertEqual("", recursive_unicode(b""))
        self.assertEqual("", recursive_unicode(""))
        self.assertIsNone(recursive_unicode(None))

    def test_recursive_unicode_unicode_decode_error(self) -> None:
        """
        Test if recursive unicode raises an exception on invalid bytes.
        """
        with self.assertRaises(UnicodeDecodeError):
            recursive_unicode(b'\x80')

    def test_recursive_unicode_unicode_decode_error_ignore_errors(self) -> None:
        """
        Test if recursive unicode ignores errors on invalid bytes and returns the converted bytes by using chr().
        """
        self.assertEqual("\x80", recursive_unicode(b'\x80', ignore_errors=True))

    def test_recursive_unicode_complex_object(self) -> None:
        """
        Test if a complex object can be recursively converted to unicode.
        """
        obj = {"list": [b"binary",{}], "sub dict": {"sub list": [1, b"binary",{"": b""}]}}
        expected = {"list": ["binary", {}], "sub dict": {"sub list": [1, "binary", {"": ""}]}}

        self.assertEqual(expected, recursive_unicode(obj))
