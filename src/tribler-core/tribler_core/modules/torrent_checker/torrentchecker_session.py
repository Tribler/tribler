import logging
import random
import socket
import struct
import sys
import time
from abc import ABCMeta, abstractmethod
from asyncio import DatagramProtocol, Future, TimeoutError, ensure_future, get_event_loop

from aiohttp import ClientResponseError, ClientSession, ClientTimeout

import async_timeout

from ipv8.messaging.deprecated.encoding import add_url_params
from ipv8.taskmanager import TaskManager

from tribler_core.modules.tunnel.socks5.aiohttp_connector import Socks5Connector
from tribler_core.modules.tunnel.socks5.client import Socks5Client
from tribler_core.utilities.tracker_utils import parse_tracker_url
from tribler_core.utilities.unicode import hexlify
from tribler_core.utilities.utilities import bdecode_compat

# Although these are the actions for UDP trackers, they can still be used as
# identifiers.
TRACKER_ACTION_CONNECT = 0
TRACKER_ACTION_ANNOUNCE = 1
TRACKER_ACTION_SCRAPE = 2

MAX_INT32 = 2 ** 16 - 1

UDP_TRACKER_INIT_CONNECTION_ID = 0x41727101980

MAX_INFOHASHES_IN_SCRAPE = 60


def create_tracker_session(tracker_url, timeout, proxy, socket_manager):
    """
    Creates a tracker session with the given tracker URL.
    :param tracker_url: The given tracker URL.
    :param timeout: The timeout for the session.
    :return: The tracker session.
    """
    tracker_type, tracker_address, announce_page = parse_tracker_url(tracker_url)

    if tracker_type == 'udp':
        return UdpTrackerSession(tracker_url, tracker_address, announce_page, timeout, proxy, socket_manager)
    return HttpTrackerSession(tracker_url, tracker_address, announce_page, timeout, proxy)


class TrackerSession(TaskManager):
    __meta__ = ABCMeta

    def __init__(self, tracker_type, tracker_url, tracker_address, announce_page, timeout):
        super(TrackerSession, self).__init__()

        self._logger = logging.getLogger(self.__class__.__name__)
        # tracker type in lowercase
        self.tracker_type = tracker_type
        self.tracker_url = tracker_url
        self.tracker_address = tracker_address
        # if this is a nonempty string it starts with '/'.
        self.announce_page = announce_page
        self.timeout = timeout
        self.infohash_list = []
        self.last_contact = None

        # some flags
        self.is_initiated = False  # you cannot add requests to a session if it has been initiated
        self.is_finished = False
        self.is_failed = False

    def __str__(self):
        return "Tracker[%s, %s]" % (self.tracker_type, self.tracker_url)

    async def cleanup(self):
        """
        Sets the _infohash_list to None and returns a deferred that has succeeded.
        :return: A deferred that succeeds immediately.
        """
        await self.shutdown_task_manager()
        self.infohash_list = None

    def has_infohash(self, infohash):
        return infohash in self.infohash_list

    def add_infohash(self, infohash):
        """
        Adds an infohash into this session.
        :param infohash: The infohash to be added.
        """
        assert not self.is_initiated, "Must not add request to an initiated session."
        assert not self.has_infohash(infohash), "Must not add duplicate requests"
        if len(self.infohash_list) < MAX_INFOHASHES_IN_SCRAPE:
            self.infohash_list.append(infohash)

    def failed(self, msg=None):
        """
        This method handles everything that needs to be done when one step
        in the session has failed and thus no data can be obtained.
        """
        if not self.is_failed:
            self.is_failed = True
            result_msg = "%s tracker failed for url %s" % (self.tracker_type, self.tracker_url)
            if msg:
                result_msg += " (error: %s)" % msg
            raise ValueError(result_msg)

    @abstractmethod
    async def connect_to_tracker(self):
        """Does some work when a connection has been established."""


class HttpTrackerSession(TrackerSession):
    def __init__(self, tracker_url, tracker_address, announce_page, timeout, proxy):
        super().__init__('http', tracker_url, tracker_address, announce_page, timeout)
        self._session = ClientSession(connector=Socks5Connector(proxy) if proxy else None,
                                      raise_for_status=True,
                                      timeout=ClientTimeout(total=self.timeout))

    async def connect_to_tracker(self):
        # create the HTTP GET message
        # Note: some trackers have strange URLs, e.g.,
        #       http://moviezone.ws/announce.php?passkey=8ae51c4b47d3e7d0774a720fa511cc2a
        #       which has some sort of 'key' as parameter, so we need to use the add_url_params
        #       utility function to handle such cases.

        url = add_url_params("http://%s:%s%s" %
                             (self.tracker_address[0], self.tracker_address[1],
                              self.announce_page.replace('announce', 'scrape')),
                             {"info_hash": self.infohash_list})

        # no more requests can be appended to this session
        self.is_initiated = True
        self.last_contact = int(time.time())

        try:
            self._logger.debug("%s HTTP SCRAPE message sent: %s", self, url)
            async with self._session:
                async with self._session.get(url.encode('ascii').decode('utf-8')) as response:
                    body = await response.read()
        except UnicodeEncodeError as e:
            raise e
        except ClientResponseError as e:
            self._logger.warning("%s HTTP SCRAPE error response code %s", self, e.status)
            self.failed(msg="error code %s" % e.status)
        except Exception as e:
            self.failed(msg=str(e))

        return self._process_scrape_response(body)

    def _process_scrape_response(self, body):
        """
        This function handles the response body of a HTTP tracker,
        parsing the results.
        """
        # parse the retrieved results
        if body is None:
            self.failed(msg="no response body")

        response_dict = bdecode_compat(body)
        if not response_dict:
            self.failed(msg="no valid response")

        response_list = []

        unprocessed_infohash_list = self.infohash_list[:]
        if b'files' in response_dict and isinstance(response_dict[b'files'], dict):
            for infohash in response_dict[b'files']:
                complete = 0
                incomplete = 0
                if isinstance(response_dict[b'files'][infohash], dict):
                    complete = response_dict[b'files'][infohash].get(b'complete', 0)
                    incomplete = response_dict[b'files'][infohash].get(b'incomplete', 0)

                # Sow complete as seeders. "complete: number of peers with the entire file, i.e. seeders (integer)"
                #  - https://wiki.theory.org/BitTorrentSpecification#Tracker_.27scrape.27_Convention
                seeders = complete
                leechers = incomplete

                # Store the information in the dictionary
                response_list.append({'infohash': hexlify(infohash), 'seeders': seeders, 'leechers': leechers})

                # remove this infohash in the infohash list of this session
                if infohash in unprocessed_infohash_list:
                    unprocessed_infohash_list.remove(infohash)

        elif b'failure reason' in response_dict:
            self._logger.info("%s Failure as reported by tracker [%s]", self, repr(response_dict[b'failure reason']))
            self.failed(msg=repr(response_dict[b'failure reason']))

        # handle the infohashes with no result (seeders/leechers = 0/0)
        for infohash in unprocessed_infohash_list:
            response_list.append({'infohash': hexlify(infohash), 'seeders': 0, 'leechers': 0})

        self.is_finished = True
        return {self.tracker_url: response_list}

    async def cleanup(self):
        """
        Cleans the session by cancelling all deferreds and closing sockets.
        :return: A deferred that fires once the cleanup is done.
        """
        await self._session.close()
        await super(HttpTrackerSession, self).cleanup()


class UdpSocketManager(DatagramProtocol):
    """
    The UdpSocketManager ensures that the network packets are forwarded to the right UdpTrackerSession.
    """

    def __init__(self):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.tracker_sessions = {}
        self.transport = None
        self.proxy_transports = {}

    def connection_made(self, transport):
        self.transport = transport

    async def send_request(self, data, tracker_session):
        transport = self.transport
        proxy = tracker_session.proxy

        if proxy:
            transport = self.proxy_transports.get(proxy, Socks5Client(proxy, self.datagram_received))
            if not transport.associated:
                await transport.associate_udp()
            if proxy not in self.proxy_transports:
                self.proxy_transports[proxy] = transport

        try:
            transport.sendto(data, (tracker_session.ip_address, tracker_session.port))
            f = self.tracker_sessions[tracker_session.transaction_id] = Future()
            return await f
        except socket.error as e:
            self._logger.warning("Unable to write data to %s:%d - %s",
                                 tracker_session.ip_address, tracker_session.port, e)
            return RuntimeError("Unable to write to socket - " + str(e))

    def datagram_received(self, data, _):
        # If the incoming data is valid, find the tracker session and give it the data
        if data and len(data) >= 4:
            transaction_id = struct.unpack_from('!i', data, 4)[0]
            if transaction_id in self.tracker_sessions:
                session = self.tracker_sessions.pop(transaction_id)
                if not session.done():
                    session.set_result(data)


class UdpTrackerSession(TrackerSession):
    """
    The UDPTrackerSession makes a connection with a UDP tracker and queries
    seeders and leechers for one or more infohashes. It handles the message serialization
    and communication with the torrent checker by making use of Deferred (asynchronously).
    """

    # A list of transaction IDs that have been used in order to avoid conflict.
    _active_session_dict = dict()

    def __init__(self, tracker_url, tracker_address, announce_page, timeout, proxy, socket_mgr):
        super().__init__('udp', tracker_url, tracker_address, announce_page, timeout)

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

    def generate_transaction_id(self):
        """
        Generates a unique transaction id and stores this in the _active_session_dict set.
        """
        while True:
            # make sure there is no duplicated transaction IDs
            transaction_id = random.randint(0, MAX_INT32)
            if transaction_id not in UdpTrackerSession._active_session_dict.items():
                UdpTrackerSession._active_session_dict[self] = transaction_id
                self.transaction_id = transaction_id
                break

    def remove_transaction_id(self):
        """
        Removes an session and its corresponding id from the _active_session_dict set and the socket manager.
        :param session: The session that needs to be removed from the set.
        """
        if self in UdpTrackerSession._active_session_dict:
            del UdpTrackerSession._active_session_dict[self]

        # Checking for socket_mgr is a workaround for race condition
        # in Tribler Session startup/shutdown that sometimes causes
        # unit tests to fail on teardown.
        if self.socket_mgr and self.transaction_id in self.socket_mgr.tracker_sessions:
            self.socket_mgr.tracker_sessions.pop(self.transaction_id)

    async def cleanup(self):
        """
        Cleans the session by cancelling all deferreds and closing sockets.
        :return: A deferred that fires once the cleanup is done.
        """
        await super(UdpTrackerSession, self).cleanup()
        self.remove_transaction_id()

    async def connect_to_tracker(self):
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
                # Resolve the hostname to an IP address if not done already
                coro = get_event_loop().getaddrinfo(self.tracker_address[0], 0, family=socket.AF_INET)
                if isinstance(coro, Future):
                    infos = await coro  # In Python <=3.6 getaddrinfo returns a Future
                else:
                    infos = await self.register_anonymous_task("resolve", ensure_future(coro))
                self.ip_address = infos[0][-1][0]
                await self.connect()
                return await self.scrape()
        except TimeoutError:
            self.failed(msg='request timed out')
        except socket.gaierror as e:
            self.failed(msg=str(e))

    async def connect(self):
        """
        Creates a connection message and calls the socket manager to send it.
        """
        if not self.socket_mgr.transport:
            self.failed(msg="UDP socket transport not ready")

        # Initiate the connection
        message = struct.pack('!qii', self._connection_id, self.action, self.transaction_id)
        response = await self.socket_mgr.send_request(message, self)

        # check message size
        if len(response) < 16:
            self._logger.error("%s Invalid response for UDP CONNECT: %s", self, repr(response))
            self.failed(msg="invalid response size")

        # check the response
        action, transaction_id = struct.unpack_from('!ii', response, 0)
        if action != self.action or transaction_id != self.transaction_id:
            # get error message
            errmsg_length = len(response) - 8
            error_message, = struct.unpack_from('!' + str(errmsg_length) + 's', response, 8)

            self._logger.info("%s Error response for UDP CONNECT [%s]: %s",
                              self, repr(response), repr(error_message))
            self.failed(msg=error_message.decode('utf8', errors='ignore'))

        # update action and IDs
        self._connection_id = struct.unpack_from('!q', response, 8)[0]
        self.action = TRACKER_ACTION_SCRAPE
        self.generate_transaction_id()
        self.last_contact = int(time.time())

    async def scrape(self):
        # pack and send the message
        if sys.version_info.major > 2:
            infohash_list = self.infohash_list
        else:
            infohash_list = [str(infohash) for infohash in self.infohash_list]

        fmt = '!qii' + ('20s' * len(self.infohash_list))
        message = struct.pack(fmt, self._connection_id, self.action, self.transaction_id, *infohash_list)

        # Send the scrape message
        response = await self.socket_mgr.send_request(message, self)

        # check message size
        if len(response) < 8:
            self._logger.info("%s Invalid response for UDP SCRAPE: %s", self, repr(response))
            self.failed("invalid message size")

        # check response
        action, transaction_id = struct.unpack_from('!ii', response, 0)
        if action != self.action or transaction_id != self.transaction_id:
            # get error message
            errmsg_length = len(response) - 8
            error_message, = struct.unpack_from('!' + str(errmsg_length) + 's', response, 8)

            self._logger.info("%s Error response for UDP SCRAPE: [%s] [%s]",
                              self, repr(response), repr(error_message))
            self.failed(msg=error_message.decode('utf8', errors='ignore'))

        # get results
        if len(response) - 8 != len(self.infohash_list) * 12:
            self._logger.info("%s UDP SCRAPE response mismatch: %s", self, len(response))
            self.failed(msg="invalid response size")

        offset = 8

        response_list = []

        for infohash in self.infohash_list:
            complete, _downloaded, incomplete = struct.unpack_from('!iii', response, offset)
            offset += 12

            # Store the information in the hash dict to be returned.
            # Sow complete as seeders. "complete: number of peers with the entire file, i.e. seeders (integer)"
            #  - https://wiki.theory.org/BitTorrentSpecification#Tracker_.27scrape.27_Convention
            response_list.append({'infohash': hexlify(infohash),
                                  'seeders': complete, 'leechers': incomplete})

        # close this socket and remove its transaction ID from the list
        self.remove_transaction_id()
        self.last_contact = int(time.time())
        self.is_finished = True

        return {self.tracker_url: response_list}


class FakeDHTSession(TrackerSession):
    """
    Fake TrackerSession that manages DHT requests
    """

    def __init__(self, session, infohash, timeout):
        super().__init__('DHT', 'DHT', 'DHT', 'DHT', timeout)

        self.infohash = infohash
        self._session = session

    async def cleanup(self):
        """
        Cleans the session by cancelling all deferreds and closing sockets.
        :return: A deferred that fires once the cleanup is done.
        """
        self.infohash_list = None
        self._session = None

    def add_infohash(self, infohash):
        """
        This function adds a infohash to the request list.
        :param infohash: The infohash to be added.
        """
        self.infohash = infohash

    async def connect_to_tracker(self):
        """
        Fakely connects to a tracker.
        :return: A deferred that fires with the health information.
        """
        metainfo = await self._session.dlmgr.get_metainfo(self.infohash, timeout=self.timeout)
        if not metainfo:
            raise RuntimeError("Metainfo lookup error")

        return {
            "DHT": [{
                "infohash": hexlify(self.infohash),
                "seeders": metainfo[b"seeders"],
                "leechers": metainfo[b"leechers"]
            }]
        }


class FakeBep33DHTSession(FakeDHTSession):
    """
    Fake session for a BEP33 lookup.
    """

    async def connect_to_tracker(self):
        """
        Fakely connects to a tracker.
        :return: A deferred that fires with the health information.
        """
        try:
            async with async_timeout.timeout(self.timeout):
                return await self._session.dlmgr.dht_health_manager.get_health(self.infohash)
        except TimeoutError:
            self.failed(msg='request timed out')
