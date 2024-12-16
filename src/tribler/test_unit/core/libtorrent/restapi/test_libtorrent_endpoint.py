from asyncio import Future, ensure_future, sleep
from binascii import hexlify
from unittest.mock import Mock

from ipv8.test.base import TestBase
from ipv8.test.REST.rest_base import MockRequest, response_to_json

from tribler.core.libtorrent.restapi.libtorrent_endpoint import LibTorrentEndpoint


class TestLibTorrentEndpoint(TestBase):
    """
    Tests for the LibTorrentEndpoint class.
    """

    def setUp(self) -> None:
        """
        Create a mocked DownloadManager and a CreateTorrentEndpoint.
        """
        super().setUp()

        self.download_manager = Mock()
        self.endpoint = LibTorrentEndpoint(self.download_manager)

    async def test_get_settings_unknown_unspecified_hops_default(self) -> None:
        """
        Test if getting settings for an unspecified number of hops defaults to 0 hops.
        """
        self.download_manager.ltsessions = {}
        request = MockRequest("/api/libtorrent/settings", query={})

        response = await self.endpoint.get_libtorrent_settings(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertEqual(0, response_body_json["hop"])
        self.assertEqual({}, response_body_json["settings"])

    async def test_get_settings_unknown_specified_hops_default(self) -> None:
        """
        Test if getting settings for an unknown number of hops defaults to 0 hops.
        """
        self.download_manager.ltsessions = {}
        request = MockRequest("/api/libtorrent/settings", query={"hop": 1})

        response = await self.endpoint.get_libtorrent_settings(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertEqual(1, response_body_json["hop"])
        self.assertEqual({}, response_body_json["settings"])

    async def test_get_settings_zero_hops(self) -> None:
        """
        Test if getting settings for zero hops gives extended info.
        """
        fut = Future()
        fut.set_result(Mock())
        self.download_manager.ltsessions = {0: fut}
        self.download_manager.get_session_settings = Mock(return_value={"peer_fingerprint": "test", "test": "test"})
        request = MockRequest("/api/libtorrent/settings", query={})

        response = await self.endpoint.get_libtorrent_settings(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertEqual(0, response_body_json["hop"])
        self.assertEqual("test", response_body_json["settings"]["test"])
        self.assertEqual(hexlify(b"test").decode(), response_body_json["settings"]["peer_fingerprint"])

    async def test_get_settings_more_hops(self) -> None:
        """
        Test if getting settings for more hops leaves out extended info.
        """
        fut = Future()
        fut.set_result(Mock(get_settings=Mock(return_value={"test": "test"})))
        self.download_manager.ltsessions = {2: fut}
        request = MockRequest("/api/libtorrent/settings", query={"hop": 2})

        response = await self.endpoint.get_libtorrent_settings(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertEqual(2, response_body_json["hop"])
        self.assertEqual("test", response_body_json["settings"]["test"])

    async def test_get_session_info_unknown_unspecified_hops_default(self) -> None:
        """
        Test if getting session info for an unspecified number of hops defaults to 0 hops.
        """
        self.download_manager.ltsessions = {}
        request = MockRequest("/api/libtorrent/settings")

        response = await self.endpoint.get_libtorrent_session_info(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertEqual(0, response_body_json["hop"])
        self.assertEqual({}, response_body_json["session"])

    async def test_get_session_info_unknown_specified_hops_default(self) -> None:
        """
        Test if getting session info for an unknown number of hops defaults to 0 hops.
        """
        self.download_manager.ltsessions = {}
        request = MockRequest("/api/libtorrent/settings", query={"hop": 1})

        response = await self.endpoint.get_libtorrent_session_info(request)
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertEqual(1, response_body_json["hop"])
        self.assertEqual({}, response_body_json["session"])

    async def test_get_session_info_known(self) -> None:
        """
        Test if getting session info for a known number of hops forwards the known settings.
        """
        fut = Future()
        fut.set_result(Mock())
        self.download_manager.ltsessions = {0: fut}
        request = MockRequest("/api/libtorrent/settings", query={})

        response_future = ensure_future(self.endpoint.get_libtorrent_session_info(request))
        await sleep(0)
        self.download_manager.session_stats_callback(Mock(values={"test": "test"}))
        response = await response_future
        response_body_json = await response_to_json(response)

        self.assertEqual(200, response.status)
        self.assertEqual(0, response_body_json["hop"])
        self.assertEqual("test", response_body_json["session"]["test"])
