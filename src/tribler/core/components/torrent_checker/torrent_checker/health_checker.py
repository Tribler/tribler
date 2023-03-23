import asyncio
from typing import Optional

from ipv8.taskmanager import TaskManager

from tribler.core.components.torrent_checker.torrent_checker.dataclasses import HealthInfo
from tribler.core.components.torrent_checker.torrent_checker.socket_manager import UdpSocketManager
from tribler.core.components.torrent_checker.torrent_checker.trackers import TrackerException
from tribler.core.components.torrent_checker.torrent_checker.trackers.dht import DHTTracker
from tribler.core.components.torrent_checker.torrent_checker.trackers.http import HttpTracker
from tribler.core.components.torrent_checker.torrent_checker.trackers.udp import UdpTracker
from tribler.core.components.torrent_checker.torrent_checker.utils import filter_non_exceptions, \
    aggregate_responses_for_infohash


class TorrentHealthChecker(TaskManager):

    def __init__(self, proxy=None):
        super().__init__()
        self.proxy = proxy
        self.socket_mgr = UdpSocketManager()
        self.udp_transport = None

        self.udp_tracker: Optional[UdpTracker] = None
        self.http_tracker: HttpTracker = HttpTracker(self.proxy)
        self.dht_tracker: DHTTracker = None

    async def initialize(self):
        await self.create_socket_or_schedule()

    async def listen_on_udp(self):
        loop = asyncio.get_event_loop()
        transport, _ = await loop.create_datagram_endpoint(lambda: self.socket_mgr, local_addr=('0.0.0.0', 0))
        return transport

    async def create_socket_or_schedule(self):
        """
        This method attempts to bind to a UDP port. If it fails for some reason (i.e. no network connection), we try
        again later.
        """
        try:
            self.udp_transport = await self.listen_on_udp()
            self.udp_tracker = UdpTracker(self.socket_mgr, proxy=self.proxy)
            self.dht_tracker = DHTTracker(self.socket_mgr, proxy=self.proxy)
        except OSError as e:
            self._logger.error("Error when creating UDP socket in torrent checker: %s", e)
            self.register_task("listen_udp_port", self.create_socket_or_schedule, delay=10)

    async def shutdown(self):
        """
        Shutdown the torrent health checker.

        Once shut down it can't be started again.
        :returns A deferred that will fire once the shutdown has completed.
        """
        if self.udp_transport:
            self.udp_transport.close()
            self.udp_transport = None

        await self.shutdown_task_manager()

    async def get_health_info(self, infohash, trackers=None, timeout=20) -> HealthInfo:
        tracker_response_coros = []
        for tracker_url in trackers:
            tracker_response_coro = self.get_tracker_response(tracker_url, [infohash], timeout=timeout)
            if tracker_response_coro:
                tracker_response_coros.append(tracker_response_coro)

        responses = await asyncio.gather(*tracker_response_coros)
        self._logger.info(f'{len(responses)} responses have been received: {responses}')
        successful_responses = filter_non_exceptions(responses)
        health = aggregate_responses_for_infohash(infohash, successful_responses)
        return health

    async def get_tracker_response(self, tracker, infohashes=None, timeout=20):
        tracker_response = None
        if tracker.startswith('udp:'):
            tracker_response = await self.udp_tracker.get_tracker_response(tracker, infohashes, timeout=timeout)
        elif tracker.startswith('http'):
            tracker_response = await self.http_tracker.get_tracker_response(tracker, infohashes, timeout=timeout)
        elif tracker.upper() == 'DHT' or not tracker:
            tracker_response = await self.dht_tracker.get_health(infohashes[0], timeout=timeout)
        else:
            raise TrackerException(f"Unknown tracker: {tracker}")

        return tracker_response
