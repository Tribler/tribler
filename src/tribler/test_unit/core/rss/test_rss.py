from time import time
from unittest.mock import AsyncMock, Mock, call, patch

from aiohttp import ClientConnectionError, ClientResponse
from ipv8.taskmanager import TaskManager
from ipv8.test.base import TestBase

import tribler
from tribler.core.notifier import Notification, Notifier
from tribler.core.rss.rss import RSSWatcher
from tribler.test_unit.core.libtorrent.mocks import TORRENT_WITH_DIRS_CONTENT


class MockWatcher(RSSWatcher):
    """
    Mocked RSSWatcher that doesn't communicate with the Internet.
    """

    def __init__(self, task_manager: TaskManager, notifier: Notifier, url: str) -> None:
        """
        Allow for mocking the conditional GET response.
        """
        super().__init__(task_manager, notifier, url)
        self.cg_response = Mock()
        self.cg_response_content = b"test"

    async def conditional_get(self, last_modified_time: float) -> tuple[ClientResponse, bytes]:
        """
        Mocked get, return fixed response.
        """
        return self.cg_response, self.cg_response_content


class TestRSSWatcher(TestBase):
    """
    Tests for the RSSWatcher class.
    """

    def setUp(self) -> None:
        """
        Create a new tracker manager and a torrent checker.
        """
        super().setUp()
        self.watcher = MockWatcher(TaskManager(), Notifier(), "localhost/rss")

    def test_restart(self) -> None:
        """
        Check for gotcha's with non-async adding and removing and task manager names.
        """
        self.watcher.start()
        self.watcher.stop()
        self.watcher.start()

        self.assertTrue(self.watcher.running)
        self.assertIsNotNone(self.watcher.task_manager.get_task("RSS watcher for localhost/rss"))

    async def test_resolve(self) -> None:
        """
        Test if torrent data can be resolved and a notification is sent.
        """
        callback = Mock()
        self.watcher.notifier.add(Notification.torrent_metadata_added, callback)

        with patch.dict(tribler.core.rss.rss.__dict__, query_uri=AsyncMock(return_value=TORRENT_WITH_DIRS_CONTENT)):
            await self.watcher.resolve({"localhost/rss"})

        args, kwargs = callback.call_args
        self.assertEqual(b"\xb3\xba\x19\xc93\xda\x95\x84k\xfd\xf7Z\xd0\x8a\x94\x9cl\xea\xc7\xbc",
                         kwargs["metadata"]["infohash"])
        self.assertEqual("torrent_create", kwargs["metadata"]["title"])

    async def test_resolve_error(self) -> None:
        """
        Test if no notification is not sent when a URL fails to resolve.
        """
        callback = Mock()
        self.watcher.notifier.add(Notification.torrent_metadata_added, callback)

        with patch.dict(tribler.core.rss.rss.__dict__, query_uri=AsyncMock(side_effect=ValueError)):
            await self.watcher.resolve({"localhost/rss"})

        self.assertIsNone(callback.call_args)

    async def test_resolve_malformed(self) -> None:
        """
        Test if no notification is not sent when a URL resolves to bad metainfo.
        """
        callback = Mock()
        self.watcher.notifier.add(Notification.torrent_metadata_added, callback)

        with patch.dict(tribler.core.rss.rss.__dict__, query_uri=AsyncMock(return_value=b"Oops: 404!")):
            await self.watcher.resolve({"localhost/rss"})

        self.assertIsNone(callback.call_args)

    async def test_skip_check(self) -> None:
        """
        Test if no notification is not sent when a URL resolves to bad metainfo.
        """
        self.watcher.next_check = time() + 999999999999999999
        self.watcher.conditional_get = Mock(side_effect=AssertionError)

        await self.watcher.check()

        self.assertIsNone(self.watcher.conditional_get.call_args)

    async def test_check_200(self) -> None:
        """
        Test if a check schedules an RSS parsing of an HTTP 200 response.
        """
        self.watcher.next_check = 0
        self.watcher.parse_rss = AsyncMock()
        self.watcher.cg_response.headers = {
            "Keep-Alive": "1337",
            "Date": "Mon, 20 Nov 1995 19:12:08 -0500"
        }
        self.watcher.cg_response.status = 200

        await self.watcher.check()

        self.assertLess(time(), self.watcher.next_check)
        self.assertEqual("Mon, 20 Nov 1995 19:12:08 -0500", self.watcher.last_modified)
        self.assertEqual(call(b"test"), self.watcher.parse_rss.call_args)

    async def test_check_304(self) -> None:
        """
        Test if a check does not schedule RSS parsing after an HTTP 304 response.
        """
        self.watcher.next_check = 0
        self.watcher.parse_rss = AsyncMock()
        self.watcher.cg_response.headers = {
            "Keep-Alive": "1337",
            "Date": "Mon, 20 Nov 1995 19:12:08 -0500"
        }
        self.watcher.cg_response.status = 304

        await self.watcher.check()

        self.assertLess(time(), self.watcher.next_check)
        self.assertEqual("Mon, 20 Nov 1995 19:12:08 -0500", self.watcher.last_modified)
        self.assertIsNone(self.watcher.parse_rss.call_args)

    async def test_check_connect_error(self) -> None:
        """
        Test if a check can deal with connection errors to trackers.
        """
        self.watcher.next_check = 0
        self.watcher.conditional_get = Mock(side_effect=ClientConnectionError)

        await self.watcher.check()

        self.assertLess(time() + 100, self.watcher.next_check)

    async def test_parse_rss_empty(self) -> None:
        """
        Test if we don't crash on parsing emtpy RSS contents.
        """
        self.watcher.resolve = AsyncMock()

        await self.watcher.parse_rss(b"")

        self.assertIsNone(self.watcher.resolve.call_args)

    async def test_parse_rss_malformed(self) -> None:
        """
        Test if we don't crash on parsing malformed RSS contents.
        """
        self.watcher.resolve = AsyncMock()

        await self.watcher.parse_rss(b"a")

        self.assertIsNone(self.watcher.resolve.call_args)

    async def test_parse_rss_unusable(self) -> None:
        """
        Test if we don't crash on parsing unusable (no .torrents) RSS contents.
        """
        self.watcher.resolve = AsyncMock()

        await self.watcher.parse_rss(b"<div>hi</div>")

        self.assertIsNone(self.watcher.resolve.call_args)

    async def test_parse_rss(self) -> None:
        """
        Test if we extract all .torrents from RSS contents.
        """
        self.watcher.resolve = AsyncMock()

        await self.watcher.parse_rss(b"<div>thisisa.torrent</div>")

        self.assertEqual(call({"thisisa.torrent"}), self.watcher.resolve.call_args)

    async def test_parse_rss_old(self) -> None:
        """
        Test if we ignore already-known .torrents from RSS contents.
        """
        self.watcher.resolve = AsyncMock()
        self.watcher.previous_entries = {"thisisa.torrent"}

        await self.watcher.parse_rss(b"<div>thisisa.torrent</div>")

        self.assertIsNone(self.watcher.resolve.call_args)
