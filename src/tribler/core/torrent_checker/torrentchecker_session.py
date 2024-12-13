from __future__ import annotations

import logging
import random
import socket
import struct
import time
from abc import ABCMeta, abstractmethod
from asyncio import DatagramProtocol, Future, Task, ensure_future, get_event_loop
from asyncio import TimeoutError as AsyncTimeoutError
from typing import TYPE_CHECKING, Any, List, NoReturn, cast

import async_timeout
import libtorrent as lt
from aiohttp import ClientResponseError, ClientSession, ClientTimeout
from ipv8.taskmanager import TaskManager

from tribler.core.libtorrent.trackers import add_url_params, parse_tracker_url
from tribler.core.socks5.aiohttp_connector import Socks5Connector
from tribler.core.socks5.client import Socks5Client
from tribler.core.torrent_checker.dataclasses import HealthInfo, TrackerResponse

if TYPE_CHECKING:
    from ipv8.messaging.interfaces.udp.endpoint import DomainAddress

    from tribler.core.libtorrent.download_manager import DownloadManager

# Although these are the actions for UDP trackers, they can still be used as
# identifiers.
TRACKER_ACTION_CONNECT = 0
TRACKER_ACTION_ANNOUNCE = 1
TRACKER_ACTION_SCRAPE = 2

UDP_TRACKER_INIT_CONNECTION_ID = 0x41727101980

MAX_INFOHASHES_IN_SCRAPE = 60


class TrackerSession(TaskManager):
    """
    A single session to query some (subclass) type of trackers.
    """

    __meta__ = ABCMeta

    def __init__(self, tracker_type: str, tracker_url: str, tracker_address: tuple[str, int], announce_page: str,
                 timeout: float) -> None:
        """
        Initialize the base fields of this class.
        """
        super().__init__()

        self._logger = logging.getLogger(self.__class__.__name__)
        # tracker type in lowercase
        self.tracker_type = tracker_type
        self.tracker_url = tracker_url
        self.tracker_address = tracker_address
        # if this is a nonempty string it starts with '/'.
        self.announce_page = announce_page
        self.timeout = timeout
        self.infohash_list: list[bytes] = []
        self.last_contact = 0
        self.cleanup_task: Task | None = None

        # some flags
        self.is_initiated = False  # you cannot add requests to a session if it has been initiated
        self.is_finished = False
        self.is_failed = False

    def __str__(self) -> str:
        """
        Format this class as a human-readable string.
        """
        return f"{self.__class__.__name__}[{self.tracker_type}, {self.tracker_url}]"

    async def cleanup(self) -> None:
        """
        Shutdown and invalidate.
        """
        await self.shutdown_task_manager()
        self.infohash_list = []

    def has_infohash(self, infohash: bytes) -> bool:
        """
        Whether our list of infohashes to check includes the given infohash.
        """
        return infohash in self.infohash_list

    def add_infohash(self, infohash: bytes) -> None:
        """
        Adds an infohash into this session.

        :param infohash: The infohash to be added.
        """
        assert not self.is_initiated, "Must not add request to an initiated session."
        assert not self.has_infohash(infohash), "Must not add duplicate requests"
        if len(self.infohash_list) < MAX_INFOHASHES_IN_SCRAPE:
            self.infohash_list.append(infohash)

    def failed(self, msg: str | None = None) -> NoReturn:
        """
        This method handles everything that needs to be done when one step
        in the session has failed and thus no data can be obtained.

        :raises ValueError: always.
        """
        if not self.is_failed and not self.cleanup_task:
            self.cleanup_task = ensure_future(self.cleanup())
        self.is_failed = True
        result_msg = f"{self.tracker_type} tracker failed for url {self.tracker_url}"
        if msg:
            result_msg += f" (error: {msg})"
        raise ValueError(result_msg)

    @abstractmethod
    async def connect_to_tracker(self) -> TrackerResponse:
        """Does some work when a connection has been established."""


class HttpTrackerSession(TrackerSession):
    """
    A session for HTTP tracker checks.
    """

    def __init__(self, tracker_url: str, tracker_address: tuple[str, int], announce_page: str, timeout: float,
                 proxy: tuple) -> None:
        """
        Create a new HTTP tracker session.
        """
        super().__init__("http", tracker_url, tracker_address, announce_page, timeout)
        self.session = ClientSession(connector=Socks5Connector(proxy) if proxy else None,
                                     raise_for_status=True,
                                     timeout=ClientTimeout(total=self.timeout))

    async def connect_to_tracker(self) -> TrackerResponse:
        """
        Create the HTTP GET message.
        """
        # Note: some trackers have strange URLs, e.g.,
        #       http://moviezone.ws/announce.php?passkey=8ae51c4b47d3e7d0774a720fa511cc2a
        #       which has some sort of 'key' as parameter, so we need to use the add_url_params
        #       utility function to handle such cases.

        url = add_url_params("http://{}:{}{}".format(self.tracker_address[0], self.tracker_address[1],
                              self.announce_page.replace("announce", "scrape")),
                             {"info_hash": self.infohash_list})

        # no more requests can be appended to this session
        self.is_initiated = True
        self.last_contact = int(time.time())

        try:
            self._logger.debug("%s HTTP SCRAPE message sent: %s", self, url)
            async with self.session, self.session.get(url.encode("ascii").decode()) as response:
                body = await response.read()
        except UnicodeEncodeError:
            raise
        except ClientResponseError as e:
            self._logger.warning("%s HTTP SCRAPE error response code %s", self, e.status)
            self.failed(msg=f"error code {e.status}")
        except Exception as e:
            self.failed(msg=str(e))

        return self.process_scrape_response(body)

    def process_scrape_response(self, body: bytes | None) -> TrackerResponse:
        """
        This function handles the response body of an HTTP result from an HTTP tracker.
        """
        if body is None:
            self.failed(msg="no response body")

        response_dict = cast(dict[bytes, Any], lt.bdecode(body))
        if not response_dict:
            self.failed(msg="no valid response")

        health_list: List[HealthInfo] = []
        now = int(time.time())

        unprocessed_infohashes = set(self.infohash_list)
        files = response_dict.get(b"files")
        if isinstance(files, dict):
            for infohash, file_info in files.items():
                seeders = leechers = 0
                if isinstance(file_info, dict):
                    # "complete: number of peers with the entire file, i.e. seeders (integer)"
                    #  - https://wiki.theory.org/BitTorrentSpecification#Tracker_.27scrape.27_Convention
                    seeders = file_info.get(b"complete", 0)
                    leechers = file_info.get(b"incomplete", 0)

                unprocessed_infohashes.discard(infohash)
                health_list.append(HealthInfo(infohash, seeders, leechers, last_check=now, self_checked=True))

        elif b"failure reason" in response_dict:
            self._logger.info("%s Failure as reported by tracker [%s]", self, repr(response_dict[b"failure reason"]))
            self.failed(msg=repr(response_dict[b"failure reason"]))

        # handle the infohashes with no result (seeders/leechers = 0/0)
        health_list.extend(HealthInfo(infohash=infohash, last_check=now, self_checked=True)
                           for infohash in unprocessed_infohashes)

        self.is_finished = True
        return TrackerResponse(url=self.tracker_url, torrent_health_list=health_list)

    async def cleanup(self) -> None:
        """
        Cleans the session by cancelling all deferreds and closing sockets.
        """
        await self.session.close()
        await super().cleanup()


class UdpSocketManager(DatagramProtocol):
    """
    The UdpSocketManager ensures that the network packets are forwarded to the right UdpTrackerSession.
    """

    def __init__(self) -> None:
        """
        Create a new UDP socket protocol for trackers.
        """
        self._logger = logging.getLogger(self.__class__.__name__)
        self.tracker_sessions: dict[int, Future[bytes]] = {}
        self.transport: Socks5Client | None = None
        self.proxy_transports: dict[tuple, Socks5Client] = {}

    def connection_made(self, transport: Socks5Client) -> None:
        """
        Callback for when a connection is established.
        """
        self.transport = transport

    async def send_request(self, data: bytes, tracker_session: UdpTrackerSession) -> RuntimeError | bytes:
        """
        Send a request and wait for the answer.
        """
        transport: Socks5Client | None = self.transport
        proxy = tracker_session.proxy

        if proxy:
            transport = self.proxy_transports.get(proxy, Socks5Client(proxy, self.datagram_received))
            if not transport.associated:
                await transport.associate_udp()
            if proxy not in self.proxy_transports:
                self.proxy_transports[proxy] = transport

        if transport is None:
            return RuntimeError("Unable to write without transport")

        host = tracker_session.ip_address or tracker_session.tracker_address[0]
        try:
            transport.sendto(data, (host, tracker_session.port))
            f = self.tracker_sessions[tracker_session.transaction_id] = Future()
            return await f
        except OSError as e:
            self._logger.warning("Unable to write data to %s:%d - %s",
                                 tracker_session.ip_address, tracker_session.port, e)
            return RuntimeError("Unable to write to socket - " + str(e))

    def transport_received(self, data: bytes) -> None:
        """
        If the incoming data is valid, find the tracker session and give it the data.
        """
        if data and len(data) >= 4:
            transaction_id = struct.unpack_from("!i", data, 4)[0]
            if transaction_id in self.tracker_sessions:
                session = self.tracker_sessions.pop(transaction_id)
                if not session.done():
                    session.set_result(data)

    def datagram_received(self, data: bytes, _: DomainAddress | tuple[str, int]) -> None:
        """
        If the incoming data is valid, find the tracker session and give it the data.
        """
        self.transport_received(data)


class UdpTrackerSession(TrackerSession):
    """
    The UDPTrackerSession makes a connection with a UDP tracker and queries
    seeders and leechers for one or more infohashes. It handles the message serialization
    and communication with the torrent checker by making use of Deferred (asynchronously).
    """

    # A list of transaction IDs that have been used in order to avoid conflict.
    _active_session_dict: dict[UdpTrackerSession, int] = {}

    def __init__(self, tracker_url: str, tracker_address: tuple[str, int], announce_page: str,
                 timeout: float, proxy: tuple, socket_mgr: UdpSocketManager) -> None:
        """
        Create a session for UDP trackers.
        """
        super().__init__("udp", tracker_url, tracker_address, announce_page, timeout)

        self._logger.setLevel(logging.INFO)
        self._connection_id = 0
        self.transaction_id = 0
        self.port = tracker_address[1]
        self.ip_address = None
        self.socket_mgr = socket_mgr
        self.proxy = proxy

        # prepare connection message
        self._connection_id = UDP_TRACKER_INIT_CONNECTION_ID
        self.action = TRACKER_ACTION_CONNECT
        self.generate_transaction_id()

    def generate_transaction_id(self) -> None:
        """
        Generates a unique transaction id and stores this in the _active_session_dict set.
        """
        while True:
            # make sure there is no duplicated transaction IDs
            transaction_id = random.randint(0, 2147483647)
            if transaction_id not in UdpTrackerSession._active_session_dict.values():
                UdpTrackerSession._active_session_dict[self] = transaction_id
                self.transaction_id = transaction_id
                break

    def remove_transaction_id(self) -> None:
        """
        Removes an session and its corresponding id from the _active_session_dict set and the socket manager.
        """
        if self in UdpTrackerSession._active_session_dict:
            del UdpTrackerSession._active_session_dict[self]

        # Checking for socket_mgr is a workaround for race condition
        # in Tribler Session startup/shutdown that sometimes causes
        # unit tests to fail on teardown.
        if self.socket_mgr and self.transaction_id in self.socket_mgr.tracker_sessions:
            self.socket_mgr.tracker_sessions.pop(self.transaction_id)

    async def cleanup(self) -> None:
        """
        Cleans the session by cancelling all deferreds and closing sockets.
        :return: A deferred that fires once the cleanup is done.
        """
        await super().cleanup()
        self.remove_transaction_id()

    async def connect_to_tracker(self) -> TrackerResponse:
        """
        Connects to the tracker and starts querying for seed and leech data.

        :return: A dictionary containing seed/leech information per infohash
        """
        # No more requests can be appended to this session
        self.is_initiated = True

        # Clean old tasks if present
        await self.cancel_pending_task("result")
        await self.cancel_pending_task("resolve")

        try:
            async with async_timeout.timeout(self.timeout):
                # We only resolve the hostname if we're not using a proxy.
                # If a proxy is used, the TunnelCommunity will resolve the hostname at the exit nodes.
                if not self.proxy:
                    # Resolve the hostname to an IP address if not done already
                    coro = get_event_loop().getaddrinfo(self.tracker_address[0], 0, family=socket.AF_INET)
                    if isinstance(coro, Future):
                        infos = await coro  # In Python <=3.6 getaddrinfo returns a Future
                    else:
                        infos = await self.register_anonymous_task("resolve", ensure_future(coro))
                    self.ip_address = infos[0][-1][0]
                await self.connect()
                return await self.scrape()
        except AsyncTimeoutError:
            self.failed(msg="request timed out")
        except socket.gaierror as e:
            self.failed(msg=str(e))

    async def connect(self) -> None:
        """
        Creates a connection message and calls the socket manager to send it.
        """
        if not self.socket_mgr.transport:
            self.failed(msg="UDP socket transport not ready")

        # Initiate the connection
        message = struct.pack("!qii", self._connection_id, self.action, self.transaction_id)
        raw_response = await self.socket_mgr.send_request(message, self)

        if isinstance(raw_response, Exception):
            self.failed(msg=str(raw_response))
        response = cast(bytes, raw_response)

        # check message size
        if len(response) < 16:
            self._logger.error("%s Invalid response for UDP CONNECT: %s", self, repr(response))
            self.failed(msg="invalid response size")

        # check the response
        action, transaction_id = struct.unpack_from("!ii", response, 0)
        if action != self.action or transaction_id != self.transaction_id:
            # get error message
            errmsg_length = len(response) - 8
            error_message, = struct.unpack_from("!" + str(errmsg_length) + "s", response, 8)

            self._logger.info("%s Error response for UDP CONNECT [%s]: %s",
                              self, repr(response), repr(error_message))
            self.failed(msg=error_message.decode(errors="ignore"))

        # update action and IDs
        self._connection_id = struct.unpack_from("!q", response, 8)[0]
        self.action = TRACKER_ACTION_SCRAPE
        self.generate_transaction_id()
        self.last_contact = int(time.time())

    async def scrape(self) -> TrackerResponse:
        """
        Parse the response of a tracker.
        """
        fmt = "!qii" + ("20s" * len(self.infohash_list))
        message = struct.pack(fmt, self._connection_id, self.action, self.transaction_id, *self.infohash_list)

        # Send the scrape message
        raw_response = await self.socket_mgr.send_request(message, self)
        if isinstance(raw_response, Exception):
            self.failed(msg=str(raw_response))
        response = cast(bytes, raw_response)

        # check message size
        if len(response) < 8:
            self._logger.info("%s Invalid response for UDP SCRAPE: %s", self, repr(response))
            self.failed("invalid message size")

        # check response
        action, transaction_id = struct.unpack_from("!ii", response, 0)
        if action != self.action or transaction_id != self.transaction_id:
            # get error message
            errmsg_length = len(response) - 8
            error_message, = struct.unpack_from("!" + str(errmsg_length) + "s", response, 8)

            self._logger.info("%s Error response for UDP SCRAPE: [%s] [%s]",
                              self, repr(response), repr(error_message))
            self.failed(msg=error_message.decode(errors="ignore"))

        # get results
        if len(response) - 8 != len(self.infohash_list) * 12:
            self._logger.info("%s UDP SCRAPE response mismatch: %s", self, len(response))
            self.failed(msg="invalid response size")

        offset = 8

        response_list = []
        now = int(time.time())

        for infohash in self.infohash_list:
            complete, _downloaded, incomplete = struct.unpack_from("!iii", response, offset)
            offset += 12

            # Store the information in the hash dict to be returned.
            # Sow complete as seeders. "complete: number of peers with the entire file, i.e. seeders (integer)"
            #  - https://wiki.theory.org/BitTorrentSpecification#Tracker_.27scrape.27_Convention
            response_list.append(HealthInfo(infohash, seeders=complete, leechers=incomplete,
                                            last_check=now, self_checked=True))

        # close this socket and remove its transaction ID from the list
        self.remove_transaction_id()
        self.last_contact = int(time.time())
        self.is_finished = True

        return TrackerResponse(url=self.tracker_url, torrent_health_list=response_list)


class FakeDHTSession(TrackerSession):
    """
    Fake TrackerSession that manages DHT requests.
    """

    def __init__(self, download_manager: DownloadManager, timeout: float) -> None:
        """
        Create a new fake DHT tracker session.
        """
        super().__init__("DHT", "DHT", ("DHT", 0), "DHT", timeout)

        self.download_manager = download_manager

    async def connect_to_tracker(self) -> TrackerResponse:
        """
        Query the bittorrent DHT.
        """
        health_list = []
        now = int(time.time())
        for infohash in self.infohash_list:
            metainfo = await self.download_manager.get_metainfo(infohash, timeout=self.timeout)
            if metainfo is None:
                continue
            health = HealthInfo(infohash, seeders=metainfo[b"seeders"], leechers=metainfo[b"leechers"],
                                last_check=now, self_checked=True)
            health_list.append(health)

        return TrackerResponse(url="DHT", torrent_health_list=health_list)


class FakeBep33DHTSession(FakeDHTSession):
    """
    Fake session for a BEP33 lookup.
    """

    async def connect_to_tracker(self) -> TrackerResponse:
        """
        Query the bittorrent DHT using BEP33 to avoid joining the swarm.
        """
        coros = [self.download_manager.dht_health_manager.get_health(infohash, timeout=self.timeout)
                 for infohash in self.infohash_list]
        results: list[HealthInfo] = []
        for coroutine in coros:
            local_results = [result for result in (await coroutine) if not isinstance(result, Exception)]
            results = [*results, *local_results]
        return TrackerResponse(url="DHT", torrent_health_list=results)


def create_tracker_session(tracker_url: str, timeout: float, proxy: tuple,
                           socket_manager: UdpSocketManager) -> TrackerSession:
    """
    Creates a tracker session with the given tracker URL.

    :param tracker_url: The given tracker URL.
    :param timeout: The timeout for the session.
    :return: The tracker session.
    """
    tracker_type, tracker_address, announce_page = parse_tracker_url(tracker_url)

    if tracker_type == "udp":
        return UdpTrackerSession(tracker_url, tracker_address, announce_page, timeout, proxy, socket_manager)
    return HttpTrackerSession(tracker_url, tracker_address, announce_page, timeout, proxy)
