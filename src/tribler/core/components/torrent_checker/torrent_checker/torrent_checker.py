import asyncio
import logging
import random
import time
from asyncio import CancelledError
from collections import defaultdict
from typing import Dict, List, Optional, Tuple, Union

from ipv8.taskmanager import TaskManager
from pony.orm import db_session, desc, select
from pony.utils import between

from tribler.core import notifications
from tribler.core.components.libtorrent.download_manager.download_manager import DownloadManager
from tribler.core.components.metadata_store.db.serialization import REGULAR_TORRENT
from tribler.core.components.metadata_store.db.store import MetadataStore
from tribler.core.components.torrent_checker.torrent_checker import DHT
from tribler.core.components.torrent_checker.torrent_checker.dataclasses import HEALTH_FRESHNESS_SECONDS, HealthInfo, \
    TrackerResponse
from tribler.core.components.torrent_checker.torrent_checker.torrentchecker_session import \
    FakeBep33DHTSession, FakeDHTSession, TrackerSession, UdpSocketManager, create_tracker_session
from tribler.core.components.torrent_checker.torrent_checker.tracker_manager import MAX_TRACKER_FAILURES, TrackerManager
from tribler.core.components.torrent_checker.torrent_checker.utils import aggregate_responses_for_infohash, \
    filter_non_exceptions, gather_coros
from tribler.core.config.tribler_config import TriblerConfig
from tribler.core.utilities.notifier import Notifier
from tribler.core.utilities.tracker_utils import MalformedTrackerURLException
from tribler.core.utilities.unicode import hexlify
from tribler.core.utilities.utilities import has_bep33_support, is_valid_url

TRACKER_SELECTION_INTERVAL = 1  # The interval for querying a random tracker
TORRENT_SELECTION_INTERVAL = 120  # The interval for checking the health of a random torrent
USER_CHANNEL_TORRENT_SELECTION_INTERVAL = 10 * 60  # The interval for checking the health of torrents in user's channel.
MIN_TORRENT_CHECK_INTERVAL = 900  # How much time we should wait before checking a torrent again
TORRENT_CHECK_RETRY_INTERVAL = 30  # Interval when the torrent was successfully checked for the last time
MAX_TORRENTS_CHECKED_PER_SESSION = 50

TORRENT_SELECTION_POOL_SIZE = 2  # How many torrents to check (popular or random) during periodic check
USER_CHANNEL_TORRENT_SELECTION_POOL_SIZE = 5  # How many torrents to check from user's channel during periodic check
TORRENTS_CHECKED_RETURN_SIZE = 240  # Estimated torrents checked on default 4 hours idle run


class TorrentChecker(TaskManager):
    def __init__(self,
                 config: TriblerConfig,
                 download_manager: DownloadManager,
                 notifier: Notifier,
                 tracker_manager: TrackerManager,
                 metadata_store: MetadataStore,
                 socks_listen_ports: Optional[List[int]] = None):
        super().__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self.tracker_manager = tracker_manager
        self.mds = metadata_store
        self.download_manager = download_manager
        self.notifier = notifier
        self.config = config

        self.socks_listen_ports = socks_listen_ports

        self._should_stop = False
        self._sessions = defaultdict(list)
        self.socket_mgr = UdpSocketManager()
        self.udp_transport = None

        # We keep track of the results of popular torrents checked by you.
        # The popularity community gossips this information around.
        self._torrents_checked: Optional[Dict[bytes, HealthInfo]] = None

    async def initialize(self):
        self.register_task("check random tracker", self.check_random_tracker, interval=TRACKER_SELECTION_INTERVAL)
        self.register_task("check local torrents", self.check_local_torrents, interval=TORRENT_SELECTION_INTERVAL)
        self.register_task("check channel torrents", self.check_torrents_in_user_channel,
                           interval=USER_CHANNEL_TORRENT_SELECTION_INTERVAL)
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
        except OSError as e:
            self._logger.error("Error when creating UDP socket in torrent checker: %s", e)
            self.register_task("listen_udp_port", self.create_socket_or_schedule, delay=10)

    async def shutdown(self):
        """
        Shutdown the torrent health checker.

        Once shut down it can't be started again.
        :returns A deferred that will fire once the shutdown has completed.
        """
        self._should_stop = True

        if self.udp_transport:
            self.udp_transport.close()
            self.udp_transport = None

        await self.shutdown_task_manager()

    async def check_random_tracker(self):
        """
        Calling this method will fetch a random tracker from the database, select some torrents that have this
        tracker, and perform a request to these trackers.
        Return whether the check was successful.
        """
        if self._should_stop:
            self._logger.warning("Not performing tracker check since we are shutting down")
            return

        tracker = self.get_next_tracker()
        if not tracker:
            self._logger.warning("No tracker to select from to check torrent health, skip")
            return

        # get the torrents that should be checked
        url = tracker.url
        with db_session:
            dynamic_interval = TORRENT_CHECK_RETRY_INTERVAL * (2 ** tracker.failures)
            torrents = select(ts for ts in tracker.torrents if ts.last_check + dynamic_interval < int(time.time()))
            infohashes = [t.infohash for t in torrents[:MAX_TORRENTS_CHECKED_PER_SESSION]]

        if len(infohashes) == 0:
            # We have no torrent to recheck for this tracker. Still update the last_check for this tracker.
            self._logger.info(f"No torrent to check for tracker {url}")
            self.tracker_manager.update_tracker_info(url)
            return

        try:
            session = self._create_session_for_request(url, timeout=30)
        except MalformedTrackerURLException as e:
            session = None
            # Remove the tracker from the database
            self.tracker_manager.remove_tracker(url)
            self._logger.warning(e)

        if session is None:
            self._logger.warning('A session cannot be created. The torrent check procedure has been cancelled.')
            return
        # We shuffle the list so that different infohashes are checked on subsequent scrape requests if the total
        # number of infohashes exceeds the maximum number of infohashes we check.
        random.shuffle(infohashes)
        for infohash in infohashes:
            session.add_infohash(infohash)

        self._logger.info(f"Selected {len(infohashes)} new torrents to check on random tracker: {url}")
        try:
            response = await self.get_tracker_response(session)
        except Exception as e:  # pylint: disable=broad-except
            self._logger.warning(e)
        else:
            health_list = response.torrent_health_list
            self._logger.info(f"Received {len(health_list)} health info results from tracker: {health_list}")

    async def get_tracker_response(self, session: TrackerSession) -> TrackerResponse:
        t1 = time.time()
        try:
            result = await session.connect_to_tracker()
        except CancelledError:
            self._logger.info(f"Tracker session is being cancelled: {session.tracker_url}")
            raise
        except Exception as e:
            exception_str = str(e).replace('\n]', ']')
            self._logger.warning(f"Got session error for the tracker: {session.tracker_url}\n{exception_str}")
            self.tracker_manager.update_tracker_info(session.tracker_url, False)
            raise e
        finally:
            await self.clean_session(session)

        t2 = time.time()
        self._logger.info(f"Got response from {session.__class__.__name__} in {t2 - t1:.3f} seconds: {result}")

        with db_session:
            for health in result.torrent_health_list:
                self.update_torrent_health(health)

        return result

    @property
    def torrents_checked(self) -> Dict[bytes, HealthInfo]:
        if self._torrents_checked is None:
            self._torrents_checked = self.load_torrents_checked_from_db()
            lines = '\n'.join(f'    {health}' for health in sorted(self._torrents_checked.values(),
                                                                   key=lambda health: -health.last_check))
            self._logger.info(f'Initially loaded self-checked torrents:\n{lines}')
        return self._torrents_checked

    @db_session
    def load_torrents_checked_from_db(self) -> Dict[bytes, HealthInfo]:
        result = {}
        now = int(time.time())
        last_fresh_time = now - HEALTH_FRESHNESS_SECONDS
        checked_torrents = list(self.mds.TorrentState
                                .select(lambda g: g.has_data and g.self_checked
                                                  and between(g.last_check, last_fresh_time, now))
                                .order_by(lambda g: (desc(g.seeders), g.last_check))
                                .limit(TORRENTS_CHECKED_RETURN_SIZE))

        for torrent in checked_torrents:
            result[torrent.infohash] = HealthInfo(torrent.infohash, torrent.seeders, torrent.leechers,
                                                  last_check=torrent.last_check, self_checked=True)
        return result

    @db_session
    def torrents_to_check(self):
        """
        Two categories of torrents are selected (popular & old). From the pool of selected torrents, a certain
        number of them are submitted for health check. The torrents that are within the freshness window are
        excluded from the selection considering the health information is still fresh.

        1. Popular torrents (50%)
        The indicator for popularity here is considered as the seeder count with direct proportionality
        assuming more seeders -> more popular. There could be other indicators to be introduced later.

        2. Old torrents (50%)
        By old torrents, we refer to those checked quite farther in the past, sorted by the last_check value.
        """
        last_fresh_time = time.time() - HEALTH_FRESHNESS_SECONDS
        popular_torrents = list(self.mds.TorrentState.select(lambda g: g.last_check < last_fresh_time).
                                order_by(lambda g: (desc(g.seeders), g.last_check)).limit(TORRENT_SELECTION_POOL_SIZE))

        old_torrents = list(self.mds.TorrentState.select(lambda g: g.last_check < last_fresh_time).
                            order_by(lambda g: (g.last_check, desc(g.seeders))).limit(TORRENT_SELECTION_POOL_SIZE))

        selected_torrents = popular_torrents + old_torrents
        selected_torrents = random.sample(selected_torrents, min(TORRENT_SELECTION_POOL_SIZE, len(selected_torrents)))
        return selected_torrents

    async def check_local_torrents(self) -> Tuple[List, List]:
        """
        Perform a full health check on a few popular and old torrents in the database.
        """
        selected_torrents = self.torrents_to_check()
        self._logger.info(f'Check {len(selected_torrents)} local torrents')
        coros = [self.check_torrent_health(t.infohash) for t in selected_torrents]
        results = await gather_coros(coros)
        self._logger.info(f'Results for local torrents check: {results}')
        return selected_torrents, results

    @db_session
    def torrents_to_check_in_user_channel(self):
        """
        Returns a list of outdated torrents of user's channel which
        has not been checked recently.
        """
        last_fresh_time = time.time() - HEALTH_FRESHNESS_SECONDS
        channel_torrents = list(self.mds.TorrentMetadata.select(
            lambda g: g.public_key == self.mds.my_public_key_bin
                      and g.metadata_type == REGULAR_TORRENT
                      and g.health.last_check < last_fresh_time)
                                .order_by(lambda g: g.health.last_check)
                                .limit(USER_CHANNEL_TORRENT_SELECTION_POOL_SIZE))
        return channel_torrents

    async def check_torrents_in_user_channel(self) -> List[Union[HealthInfo, BaseException]]:
        """
        Perform a full health check of torrents in user's channel
        """
        selected_torrents = self.torrents_to_check_in_user_channel()
        self._logger.info(f'Check {len(selected_torrents)} torrents in user channel')
        coros = [self.check_torrent_health(t.infohash) for t in selected_torrents]
        results = await gather_coros(coros)
        self._logger.info(f'Results for torrents in user channel: {results}')
        return results

    def get_next_tracker(self):
        while tracker := self.tracker_manager.get_next_tracker():
            url = tracker.url

            if not is_valid_url(url):
                self.tracker_manager.remove_tracker(url)
            elif tracker.failures >= MAX_TRACKER_FAILURES:
                self.tracker_manager.update_tracker_info(url, is_successful=False)
            else:
                return tracker

        return None

    def is_blacklisted_tracker(self, tracker_url):
        return tracker_url in self.tracker_manager.blacklist

    @db_session
    def get_valid_trackers_of_torrent(self, infohash):
        """ Get a set of valid trackers for torrent. Also remove any invalid torrent."""
        db_tracker_list = self.mds.TorrentState.get(infohash=infohash).trackers
        return {tracker.url for tracker in db_tracker_list
                if is_valid_url(tracker.url) and not self.is_blacklisted_tracker(tracker.url)}

    async def check_torrent_health(self, infohash: bytes, timeout=20, scrape_now=False) -> HealthInfo:
        """
        Check the health of a torrent with a given infohash.
        :param infohash: Torrent infohash.
        :param timeout: The timeout to use in the performed requests
        :param scrape_now: Flag whether we want to force scraping immediately
        """
        infohash_hex = hexlify(infohash)
        self._logger.info(f'Check health for the torrent: {infohash_hex}')
        tracker_set = []

        # We first check whether the torrent is already in the database and checked before
        with db_session:
            torrent_state = self.mds.TorrentState.get(infohash=infohash)
            if torrent_state:
                last_check = torrent_state.last_check
                time_diff = time.time() - last_check
                if time_diff < MIN_TORRENT_CHECK_INTERVAL and not scrape_now:
                    self._logger.info(f"Time interval too short, not doing torrent health check for {infohash_hex}")
                    return torrent_state.to_health()

                # get torrent's tracker list from DB
                tracker_set = self.get_valid_trackers_of_torrent(torrent_state.infohash)
                self._logger.info(f'Trackers for {infohash_hex}: {tracker_set}')

        coros = []
        for tracker_url in tracker_set:
            if session := self._create_session_for_request(tracker_url, timeout=timeout):
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
        if health.last_check == 0:  # if not zero, was already updated in get_tracker_response
            health.last_check = int(time.time())
            health.self_checked = True
            self.update_torrent_health(health)

    def _create_session_for_request(self, tracker_url, timeout=20) -> Optional[TrackerSession]:
        self._logger.debug(f'Creating a session for the request: {tracker_url}')

        required_hops = self.config.download_defaults.number_hops
        actual_hops = len(self.socks_listen_ports or [])
        if required_hops > actual_hops:
            self._logger.warning(f"Dropping the request. Required amount of hops doesn't reached. "
                                 f'Required hops: {required_hops}. Actual hops: {actual_hops}')
            return None
        proxy = ('127.0.0.1', self.socks_listen_ports[required_hops - 1]) if required_hops > 0 else None
        session = create_tracker_session(tracker_url, timeout, proxy, self.socket_mgr)
        self._logger.info(f'Tracker session has been created: {session}')
        self._sessions[tracker_url].append(session)
        return session

    async def clean_session(self, session):
        url = session.tracker_url

        self.tracker_manager.update_tracker_info(url, not session.is_failed)
        # Remove the session from our session list dictionary
        self._sessions[url].remove(session)
        if len(self._sessions[url]) == 0 and url != DHT:
            del self._sessions[url]

        await session.cleanup()
        self._logger.debug('Session has been cleaned up')

    def update_torrent_health(self, health: HealthInfo) -> bool:
        """
        Updates the torrent state in the database if it already exists, otherwise do nothing.
        Returns True if the update was successful, False otherwise.
        """
        if not health.is_valid():
            self._logger.warning(f'Invalid health info ignored: {health}')
            return False

        if not health.self_checked:
            self._logger.error(f'Self-checked torrent health expected. Got: {health}')
            return False

        self._logger.debug(f'Update torrent health: {health}')
        with db_session:
            # Update torrent state
            torrent_state = self.mds.TorrentState.get_for_update(infohash=health.infohash)
            if not torrent_state:
                self._logger.warning(f"Unknown torrent: {hexlify(health.infohash)}")
                return False

            prev_health = torrent_state.to_health()
            if not health.should_replace(prev_health):
                self._logger.info("Skip health update, the health in the database is fresher or have more seeders")
                self.notify(prev_health)  # to update UI state from "Checking..."
                return False

            torrent_state.set(seeders=health.seeders, leechers=health.leechers, last_check=health.last_check,
                              self_checked=True)

        if health.seeders > 0 or health.leechers > 0:
            self.torrents_checked[health.infohash] = health
        else:
            self.torrents_checked.pop(health.infohash, None)

        self.notify(health)
        return True

    def notify(self, health: HealthInfo):
        self.notifier[notifications.channel_entity_updated]({
            'infohash': health.infohash_hex,
            'num_seeders': health.seeders,
            'num_leechers': health.leechers,
            'last_tracker_check': health.last_check,
            'health': 'updated'
        })
