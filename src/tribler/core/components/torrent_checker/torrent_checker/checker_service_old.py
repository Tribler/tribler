import asyncio
import logging
import random
import time
from asyncio import CancelledError
from collections import defaultdict
from typing import Optional

from ipv8.taskmanager import TaskManager

from tribler.core.components.torrent_checker.torrent_checker import DHT
from tribler.core.components.torrent_checker.torrent_checker.dataclasses import TrackerResponse, HealthInfo
from tribler.core.components.torrent_checker.torrent_checker.torrentchecker_session import UdpSocketManager, \
    TrackerSession, create_tracker_session, FakeBep33DHTSession, FakeDHTSession
from tribler.core.components.torrent_checker.torrent_checker.utils import gather_coros, filter_non_exceptions, \
    aggregate_responses_for_infohash
from tribler.core.utilities.tracker_utils import MalformedTrackerURLException
from tribler.core.utilities.unicode import hexlify
from tribler.core.utilities.utilities import has_bep33_support


class CheckerService(TaskManager):

    def __init__(self, download_manager, proxy):
        super().__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self.download_manager = download_manager
        self.proxy = proxy

        self._should_stop = False
        self._sessions = defaultdict(list)
        self.socket_mgr = UdpSocketManager()
        self.udp_transport = None

    async def initialize(self):
        await self.create_socket_or_schedule()

    async def shutdown(self):
        self._should_stop = True

        if self.udp_transport:
            self.udp_transport.close()
            self.udp_transport = None

        await self.shutdown_task_manager()

    def should_stop(self):
        return self._should_stop

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
        except OSError as e:
            self._logger.error("Error when creating UDP socket in torrent checker: %s", e)
            self.register_task("listen_udp_port", self.create_socket_or_schedule, delay=10)

    async def check_tracker_with_infohashes(self, url, infohashes):
        try:
            session = self.create_session_for_request(url, timeout=30)
        except MalformedTrackerURLException as e:
            raise e

        if session is None:
            self._logger.warning('A session cannot be created. The torrent check procedure has been cancelled.')
            return

        # We shuffle the list so that different infohashes are checked on subsequent scrape requests if the total
        # number of infohashes exceeds the maximum number of infohashes we check.
        random.shuffle(infohashes)
        for infohash in infohashes:
            session.add_infohash(infohash)

        return await self.get_tracker_response(session)

    async def get_tracker_response(self, session: TrackerSession) -> TrackerResponse:
        try:
            t1 = time.time()
            result = await session.connect_to_tracker()
            t2 = time.time()
            self._logger.info(f"Got response from {session.__class__.__name__} in {t2 - t1:.3f} seconds: {result}")
        except CancelledError:
            self._logger.info(f"Tracker session is being cancelled: {session.tracker_url}")
            raise
        except Exception as e:
            exception_str = str(e).replace('\n]', ']')
            self._logger.warning(f"Got session error for the tracker: {session.tracker_url}\n{exception_str}")
            raise e
        finally:
            await self.clean_session(session)

        return result

    async def clean_session(self, session):
        url = session.tracker_url

        # Remove the session from our session list dictionary
        self._sessions[url].remove(session)
        if len(self._sessions[url]) == 0 and url != DHT:
            del self._sessions[url]

        await session.cleanup()
        self._logger.debug('Session has been cleaned up')

    def create_session_for_request(self, tracker_url, timeout=20) -> Optional[TrackerSession]:
        self._logger.debug(f'Creating a session for the request: {tracker_url}')
        session = create_tracker_session(tracker_url, timeout, self.proxy, self.socket_mgr)
        self._logger.info(f'Tracker session has been created: {session}')
        self._sessions[tracker_url].append(session)
        return session

    async def check_torrent_health(self, infohash: bytes, tracker_set, timeout=20) -> HealthInfo:
        """
        Check the health of a torrent with a given infohash.
        :param infohash: Torrent infohash.
        :param tracker_set: Trackers for the infohash.
        :param timeout: The timeout to use in the performed requests
        """
        infohash_hex = hexlify(infohash)
        self._logger.info(f'Check health for the torrent: {infohash_hex}')

        coros = []
        for tracker_url in tracker_set:
            if session := self.create_session_for_request(tracker_url, timeout=timeout):
                session.add_infohash(infohash)
                coros.append(self.get_tracker_response(session))

        session_cls = FakeBep33DHTSession if has_bep33_support() else FakeDHTSession
        session = session_cls(self.download_manager, timeout)
        session.add_infohash(infohash)
        self._logger.info(f'DHT session has been created for {infohash_hex}: {session}')
        self._sessions[DHT].append(session)

        coros.append(self.get_tracker_response(session))
        responses = await gather_coros(coros)

        self._logger.info(f'{len(responses)} responses for {infohash_hex} have been received: {responses}')
        successful_responses = filter_non_exceptions(responses)
        health = aggregate_responses_for_infohash(infohash, successful_responses)
        return health