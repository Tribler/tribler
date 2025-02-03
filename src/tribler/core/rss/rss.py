from __future__ import annotations

import contextlib
import logging
from asyncio.exceptions import TimeoutError as AsyncTimeoutError
from email.utils import formatdate, parsedate
from io import BytesIO
from ssl import SSLError
from time import mktime, time
from typing import TYPE_CHECKING
from xml.etree import ElementTree as ET
from xml.etree.ElementTree import ParseError

import libtorrent
from aiohttp import ClientConnectorError, ClientResponseError, ClientSession, ServerConnectionError
from aiohttp.web_exceptions import HTTPNotModified, HTTPOk

from tribler.core.database.orm_bindings.torrent_metadata import tdef_to_metadata_dict
from tribler.core.libtorrent.restapi.torrentinfo_endpoint import query_uri
from tribler.core.libtorrent.torrentdef import TorrentDef
from tribler.core.libtorrent.uris import unshorten
from tribler.core.notifier import Notification, Notifier

if TYPE_CHECKING:
    from http.cookies import SimpleCookie

    from aiohttp import ClientResponse
    from ipv8.taskmanager import TaskManager

logger = logging.getLogger(__name__)


class RSSWatcher:
    """
    Watch a single RSS URL and call updates when new torrents are added.
    """

    def __init__(self, task_manager: TaskManager, notifier: Notifier, url: str) -> None:
        """
        Initialize (but don't start) with a given taskmanager, callback and url.
        """
        super().__init__()

        self.url = url
        self.previous_entries: set[str] = set()

        self.cookies: SimpleCookie | None = None
        self.last_modified: str | None = None
        self.next_check: float = 0.0

        self.task_manager = task_manager
        self.notifier = notifier

        self.running: bool = False

    def start(self) -> None:
        """
        Start periodically querying our URL.
        """
        task = self.task_manager.register_task(f"RSS watcher for {self.url}", self.check, interval=60.0)
        self.running = hasattr(task, "get_name")

    def stop(self) -> None:
        """
        Stop periodically querying our URL.
        """
        if self.running:
            self.task_manager.cancel_pending_task(f"RSS watcher for {self.url}")

    async def resolve(self, urls: set[str]) -> None:
        """
        Download the torrent files and add them to our database.
        """
        for url in urls:
            try:
                uri = await unshorten(url)
                response = await query_uri(uri, valid_cert=False)
            except (ServerConnectionError, ClientResponseError, SSLError, ClientConnectorError,
                    AsyncTimeoutError, ValueError) as e:
                logger.warning("Error while querying http uri: %s", str(e))
                continue

            try:
                metainfo = libtorrent.bdecode(response)
            except RuntimeError as e:
                logger.warning("Error while reading http uri response: %s", str(e))
                continue

            torrent_def = TorrentDef.load_from_dict(metainfo)
            metadata_dict = tdef_to_metadata_dict(torrent_def)
            self.notifier.notify(Notification.torrent_metadata_added, metadata=metadata_dict)

    async def conditional_get(self, last_modified_time: float) -> tuple[ClientResponse, bytes]:
        """
        Send a conditional get to our URL and return the response and its raw content.
        """
        headers = {"If-Modified-Since": formatdate(timeval=last_modified_time, localtime=False, usegmt=True)}
        async with ClientSession(None, headers=headers) as session, \
                session.get(self.url, cookies=self.cookies) as response:
            return response, await response.read()

    async def check(self) -> None:
        """
        Check our URL as lazily as possible.
        """
        if time() < self.next_check:
            logger.info("Skipping check, server requested backoff")
            return

        # Try to be kind to the server and perform a conditional HTTP GET.
        # If supported, the server will answer with a HTTP 304 error code when we don't need to do anything.
        if self.last_modified and (parsed_date := parsedate(self.last_modified)):
            last_modified_time = mktime(parsed_date)
        else:
            last_modified_time = 0

        try:
            response, content = await self.conditional_get(last_modified_time)
        except Exception as e:
            logger.exception("Retrieving %s failed with: %s", self.url, e.__class__.__name__)
            self.next_check = time() + 120  # Default timeout
            return

        # Determine the back-off requested by the server.
        refresh_timeout_min = 120
        for h_keep_alive in response.headers.get("Keep-Alive", "").split(","):
            if h_keep_alive.startswith("timeout"):
                values = h_keep_alive.split("=")[1:]
                if len(values) == 1:
                    with contextlib.suppress(ValueError):
                        refresh_timeout_min = int(values[0])
                        logger.info("%s requested timeout of %d seconds", self.url, refresh_timeout_min)
        self.next_check = time() + refresh_timeout_min
        self.last_modified = response.headers.get("Date")

        if response.status == HTTPOk.status_code:
            await self.parse_rss(content)
        elif response.status == HTTPNotModified.status_code:
            logger.info("%s conditional GET flagged no new content", self.url)

    async def parse_rss(self, content: bytes) -> None:
        """
        Check if the RSS content includes any new ``.torrent`` values.
        """
        out = set()
        with contextlib.suppress(ParseError):
            tree = ET.parse(BytesIO(content))  # noqa: S314
            for child in tree.iter():
                value = child.text
                if value and value.endswith(".torrent"):
                    out.add(value)
        new_entries = out - self.previous_entries
        self.previous_entries = out
        if new_entries:
            await self.resolve(new_entries)


class RSSWatcherManager:
    """
    Manage multiple RSS URL watchers.

    Allowed in the URL list:
     - Empty RSS feeds, for user spacing/organization. Resolved here.
     - Duplicate RSS feeds. Resolved here.
     - Unreachable RSS feeds. Resolved in ``RSSWatcher``.
    """

    def __init__(self, task_manager: TaskManager, notifier: Notifier, urls: list[str]) -> None:
        """
        Initialize (but don't start) with a given taskmanager, callback and urls.
        """
        super().__init__()

        self.task_manager = task_manager
        self.notifier = notifier
        self.watchers = {url: RSSWatcher(task_manager, notifier, url) for url in set(urls) if url}

    def start(self) -> None:
        """
        Start all our watchers.
        """
        for watcher in self.watchers.values():
            watcher.start()

    def stop(self) -> None:
        """
        Stop all our watchers.
        """
        for watcher in self.watchers.values():
            watcher.stop()
        self.watchers.clear()

    def update(self, urls: list[str]) -> None:
        """
        Update the RSS URLs that we are watching. Start and stop watchers accordingly.
        """
        started = [url for url in set(urls) if url and url not in self.watchers]
        stopped = [url for url in self.watchers if url not in urls]
        for url in stopped:
            watcher = self.watchers.pop(url)
            watcher.stop()
        for url in started:
            watcher = RSSWatcher(self.task_manager, self.notifier, url)
            self.watchers[url] = watcher
            watcher.start()
