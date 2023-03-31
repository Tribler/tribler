import logging
import socket
import struct
import time
from asyncio import get_event_loop, Future
from asyncio.exceptions import TimeoutError

import async_timeout

from tribler.core.components.torrent_checker.torrent_checker.dataclasses import TrackerResponse, UdpRequest, HealthInfo, \
    UdpRequestType
from tribler.core.components.torrent_checker.torrent_checker.socket_manager import UdpSocketManager
from tribler.core.components.torrent_checker.torrent_checker.trackers import Tracker, TrackerException
from tribler.core.utilities.tracker_utils import parse_tracker_url, MalformedTrackerURLException

TRACKER_ACTION_CONNECT = 0
TRACKER_ACTION_ANNOUNCE = 1
TRACKER_ACTION_SCRAPE = 2

MAX_INT32 = 2 ** 16 - 1

UDP_TRACKER_INIT_CONNECTION_ID = 0x41727101980


class UdpTracker(Tracker):

    def __init__(self, socket_manager: UdpSocketManager, proxy=None):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.socket_manager = socket_manager
        self.proxy = proxy

        self.transaction_id = 0

    async def get_tracker_response(self, tracker_url, infohashes, timeout=20) -> TrackerResponse:
        if not self.socket_manager or not self.socket_manager.transport:
            raise TrackerException("UDP socket transport is not ready yet")

        try:
            tracker_type, tracker_address, announce_page = parse_tracker_url(tracker_url)
        except MalformedTrackerURLException as e:
            raise TrackerException(f"Invalid tracker URL: {tracker_url}") from e

        try:
            async with async_timeout.timeout(timeout):
                ip_address = await self.resolve_ip(tracker_address)
                port = int(tracker_address[1])

                connection_id = await self.connect_to_tracker(ip_address, port)
                response_list = await self.scrape_response(ip_address, port, connection_id, infohashes)
                return TrackerResponse(url=tracker_url, torrent_health_list=response_list)

        except TimeoutError as e:
            raise TrackerException(f"Request timeout returning tracker response for {tracker_url}") from e

    async def resolve_ip(self, tracker_address):
        # We only resolve the hostname if we're not using a proxy.
        # If a proxy is used, the TunnelCommunity will resolve the hostname at the exit nodes.
        if self.proxy:
            return tracker_address[0]

        try:
            infos = await get_event_loop().getaddrinfo(tracker_address[0], 0, family=socket.AF_INET)
            ip_address = infos[0][-1][0]
            return ip_address
        except socket.gaierror as e:
            raise TrackerException("Socket error resolving tracker ip") from e

    def compose_connect_request(self, host, port, transaction_id):
        message = self.pack_connection_request(transaction_id)
        receiver = (host, port)

        udp_request = UdpRequest(
            request_type=UdpRequestType.CONNECTION_REQUEST,
            transaction_id=transaction_id,
            receiver=receiver,
            data=message,
            socks_proxy=self.proxy,
            response=Future()
        )
        return udp_request

    async def connect_to_tracker(self, ip_address, port):
        connection_request = self.compose_connect_request(ip_address, port, self.transaction_id)
        self.transaction_id += 1

        await self.socket_manager.send(connection_request, response_callback=self.await_process_connection_response)
        return await connection_request.response

    async def await_process_connection_response(self, connection_request: UdpRequest, response):
        response_future = connection_request.response
        try:
            await self.process_connection_response(connection_request, response)
        except Exception as ex:
            response_future.set_exception(ex)

    async def process_connection_response(self, connection_request: UdpRequest, response):
        action, transaction_id, connection_id = self.unpack_connection_response(response)

        if action != TRACKER_ACTION_CONNECT or transaction_id != connection_request.transaction_id:
            errmsg_length = len(response) - 8
            error_message, = struct.unpack_from('!' + str(errmsg_length) + 's', response, 8)
            self._logger.info("Invalid UDP Connect response: %s", repr(error_message))
            raise TrackerException(f"Invalid UDP Connect response: {error_message}")

        response_future = connection_request.response
        if not response_future.done():
            connection_request.response.set_result(connection_id)

    def pack_connection_request(self, transaction_id):
        connection_init_id = UDP_TRACKER_INIT_CONNECTION_ID
        action = TRACKER_ACTION_CONNECT
        return struct.pack('!qii', connection_init_id, action, transaction_id)

    def unpack_connection_response(self, response):
        if len(response) < 16:
            self._logger.error("%s Invalid response for UDP CONNECT: %s", self, repr(response))
            raise TrackerException("Invalid response size")

        action, transaction_id = struct.unpack_from('!ii', response, 0)
        connection_id = struct.unpack_from('!q', response, 8)[0]

        return action, transaction_id, connection_id

    def compose_scrape_request(self, host, port, transaction_id, connection_id, infohash_list):
        action = TRACKER_ACTION_SCRAPE
        fmt = '!qii' + ('20s' * len(infohash_list))
        message = struct.pack(fmt, connection_id, action, transaction_id, *infohash_list)
        receiver = (host, port)

        udp_request = UdpRequest(
            request_type=UdpRequestType.SCRAPE_REQUEST,
            transaction_id=transaction_id,
            receiver=receiver,
            data=message,
            connection_id=connection_id,
            socks_proxy=self.proxy,
            infohashes=infohash_list,
            response=Future()
        )
        return udp_request

    async def scrape_response(self, ip_address, port, connection_id, infohashes):
        scrape_request = self.compose_scrape_request(ip_address, port, self.transaction_id, connection_id, infohashes)
        self.transaction_id += 1

        await self.socket_manager.send(scrape_request, response_callback=self.await_process_scrape_response)
        return await scrape_request.response

    async def await_process_scrape_response(self, scrape_request: UdpRequest, response):
        response_future = scrape_request.response
        try:
            await self.process_scrape_response(scrape_request, response)
        except Exception as ex:
            response_future.set_exception(ex)

    async def process_scrape_response(self, scrape_request: UdpRequest, response):
        action, transaction_id, health_info_tuples = self.unpack_scrape_response(response)

        if action != TRACKER_ACTION_SCRAPE or transaction_id != scrape_request.transaction_id:
            errmsg_length = len(response) - 8
            error_message, = struct.unpack_from('!' + str(errmsg_length) + 's', response, 8)
            decoded_error_message = error_message.decode('utf-8')
            raise TrackerException(f"Invalid UDP scrape response: {decoded_error_message}")

        requested_infohashes = scrape_request.infohashes
        if len(requested_infohashes) != len(health_info_tuples):
            raise TrackerException(f"Invalid UDP scrape response; Number of health info requested mismatch")

        now = int(time.time())
        response_list = []

        for index, infohash in enumerate(requested_infohashes):
            complete, _downloaded, incomplete = health_info_tuples[index]
            health_info = HealthInfo(infohash, last_check=now, seeders=complete, leechers=incomplete, self_checked=True)
            response_list.append(health_info)

        response_future = scrape_request.response
        if not response_future.done():
            scrape_request.response.set_result(response_list)

    def pack_scrape_request(self):
        pass

    def unpack_scrape_response(self, response):
        if len(response) < 8:
            self._logger.info("%s Invalid response for UDP SCRAPE: %s", self, repr(response))
            raise TrackerException("Invalid message size of scrape response")

        action, transaction_id = struct.unpack_from('!ii', response, 0)

        initial_offset = 8
        health_info_size_per_infohash = 12

        health_info_bytes_of_response = response[initial_offset:]
        health_info_size_of_response = len(health_info_bytes_of_response)

        if health_info_size_of_response % health_info_size_per_infohash != 0:
            self._logger.info("%s UDP SCRAPE response mismatch: %s", self, len(response))
            raise TrackerException("Invalid UDP tracker response size")

        num_torrents = health_info_size_of_response // health_info_size_per_infohash

        health_infos = []
        offset = initial_offset
        for _ in range(num_torrents):
            complete, _downloaded, incomplete = struct.unpack_from('!iii', response, offset)
            health_infos.append((complete, _downloaded, incomplete))
            offset += 12

        return action, transaction_id, health_infos
