import asyncio
import logging
import random
import time
from asyncio import CancelledError, gather
from typing import List, Optional

from ipv8.taskmanager import TaskManager, task

from pony.orm import db_session, desc, select

from tribler_common.simpledefs import NTFY

from tribler_core.components.libtorrent.download_manager.download_manager import DownloadManager
from tribler_core.components.metadata_store.db.serialization import REGULAR_TORRENT
from tribler_core.components.metadata_store.db.store import MetadataStore
from tribler_core.components.torrent_checker.torrent_checker.torrentchecker_session import (
    FakeBep33DHTSession,
    FakeDHTSession,
    UdpSocketManager,
    create_tracker_session,
)
from tribler_core.components.torrent_checker.torrent_checker.tracker_manager import MAX_TRACKER_FAILURES, TrackerManager
from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.notifier import Notifier
from tribler_core.utilities.tracker_utils import MalformedTrackerURLException
from tribler_core.utilities.unicode import hexlify
from tribler_core.utilities.utilities import has_bep33_support, is_valid_url

TRACKER_SELECTION_INTERVAL = 20  # The interval for querying a random tracker
TORRENT_SELECTION_INTERVAL = 120  # The interval for checking the health of a random torrent
USER_CHANNEL_TORRENT_SELECTION_INTERVAL = 15  # The interval for checking the health of torrents in user's channel.
MIN_TORRENT_CHECK_INTERVAL = 900  # How much time we should wait before checking a torrent again
TORRENT_CHECK_RETRY_INTERVAL = 30  # Interval when the torrent was successfully checked for the last time
MAX_TORRENTS_CHECKED_PER_SESSION = 50

TORRENT_SELECTION_POOL_SIZE = 2  # How many torrents to check (popular or random) during periodic check
USER_CHANNEL_TORRENT_SELECTION_POOL_SIZE = 5  # How many torrents to check from user's channel during periodic check
HEALTH_FRESHNESS_SECONDS = 4 * 3600  # Number of seconds before a torrent health is considered stale. Default: 4 hours
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
        self.dlmgr = download_manager
        self.notifier = notifier
        self.config = config

        self.socks_listen_ports = socks_listen_ports

        self._should_stop = False
        self._session_list = {'DHT': []}

        self.socket_mgr = UdpSocketManager()
        self.udp_transport = None

        # We keep track of the results of popular torrents checked by you.
        # The popularity community gossips this information around.
        self._torrents_checked = dict()

    async def initialize(self):
        self.register_task("tracker_check", self.check_random_tracker, interval=TRACKER_SELECTION_INTERVAL)
        self.register_task("torrent_check", self.check_local_torrents, interval=TORRENT_SELECTION_INTERVAL)
        self.register_task("user_channel_torrent_check", self.check_torrents_in_user_channel,
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
            return False

        tracker = self.get_valid_next_tracker_for_auto_check()
        if tracker is None:
            self._logger.warning("No tracker to select from, skip")
            return False

        self._logger.debug("Start selecting torrents on tracker %s.", tracker.url)

        # get the torrents that should be checked
        with db_session:
            dynamic_interval = TORRENT_CHECK_RETRY_INTERVAL * (2 ** tracker.failures)
            # FIXME: this is a really dumb fix for update_tracker_info not being called in some cases
            if tracker.failures >= MAX_TRACKER_FAILURES:
                self.update_tracker_info(tracker.url, False)
                return False
            torrents = select(ts for ts in tracker.torrents if ts.last_check + dynamic_interval < int(time.time()))
            infohashes = [t.infohash for t in torrents[:MAX_TORRENTS_CHECKED_PER_SESSION]]

        if len(infohashes) == 0:
            # We have no torrent to recheck for this tracker. Still update the last_check for this tracker.
            self._logger.info("No torrent to check for tracker %s", tracker.url)
            self.update_tracker_info(tracker.url, True)
            return False

        try:
            session = self._create_session_for_request(tracker.url, timeout=30)
            if session is None:
                return False
        except MalformedTrackerURLException as e:
            # Remove the tracker from the database
            self.remove_tracker(tracker.url)
            self._logger.error(e)
            return False

        # We shuffle the list so that different infohashes are checked on subsequent scrape requests if the total
        # number of infohashes exceeds the maximum number of infohashes we check.
        random.shuffle(infohashes)
        for infohash in infohashes:
            session.add_infohash(infohash)

        self._logger.info("Selected %d new torrents to check on tracker: %s", len(infohashes), tracker.url)
        try:
            await self.connect_to_tracker(session)
            return True
        except:
            return False

    async def connect_to_tracker(self, session):
        try:
            info_dict = await session.connect_to_tracker()
            return await self._on_result_from_session(session, info_dict)
        except CancelledError:
            self._logger.info("Tracker session is being cancelled (url %s)", session.tracker_url)
            await self.clean_session(session)
        except Exception as e:
            self._logger.warning("Got session error for URL %s: %s", session.tracker_url, str(e).replace('\n]', ']'))
            await self.clean_session(session)
            self.tracker_manager.update_tracker_info(session.tracker_url, False)
            e.tracker_url = session.tracker_url
            raise e

    @property
    def torrents_checked(self):
        if not self._torrents_checked:
            self.load_torrents_checked_from_db()
        return self._torrents_checked.values()

    @db_session
    def load_torrents_checked_from_db(self):
        last_fresh_time = time.time() - HEALTH_FRESHNESS_SECONDS
        checked_torrents = list(self.mds.TorrentState
                                .select(lambda g: g.has_data and g.last_check > last_fresh_time and g.self_checked)
                                .order_by(lambda g: (desc(g.seeders), g.last_check))
                                .limit(TORRENTS_CHECKED_RETURN_SIZE))

        for torrent in checked_torrents:
            self._torrents_checked[torrent.infohash] = (torrent.infohash, torrent.seeders, torrent.leechers,
                                                        torrent.last_check)

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

    @db_session
    def check_local_torrents(self):
        """
        Perform a full health check on a few popular and old torrents in the database.
        """
        selected_torrents = self.torrents_to_check()

        infohashes = []
        for random_torrent in selected_torrents:
            self.check_torrent_health(bytes(random_torrent.infohash))
            infohashes.append(random_torrent.infohash)
        return infohashes

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

    @db_session
    def check_torrents_in_user_channel(self):
        """
        Perform a full health check of torrents in user's channel
        """
        for channel_torrent in self.torrents_to_check_in_user_channel():
            self.check_torrent_health(channel_torrent.infohash)

    def get_valid_next_tracker_for_auto_check(self):
        tracker = self.get_next_tracker_for_auto_check()
        while tracker and not is_valid_url(tracker.url):
            self.remove_tracker(tracker.url)
            tracker = self.get_next_tracker_for_auto_check()
        return tracker

    def get_next_tracker_for_auto_check(self):
        return self.tracker_manager.get_next_tracker_for_auto_check()

    def remove_tracker(self, tracker_url):
        self.tracker_manager.remove_tracker(tracker_url)

    def update_tracker_info(self, tracker_url, is_successful):
        self.tracker_manager.update_tracker_info(tracker_url, is_successful)

    def is_blacklisted_tracker(self, tracker_url):
        return tracker_url in self.tracker_manager.blacklist

    @db_session
    def get_valid_trackers_of_torrent(self, torrent_id):
        """ Get a set of valid trackers for torrent. Also remove any invalid torrent."""
        db_tracker_list = self.mds.TorrentState.get(infohash=torrent_id).trackers
        return {tracker.url for tracker in db_tracker_list
                if is_valid_url(tracker.url) and not self.is_blacklisted_tracker(tracker.url)}

    def update_torrents_checked(self, new_result):
        """
        Update the set with torrents that we have checked ourselves.
        """
        infohash = new_result['infohash']
        seeders = new_result['seeders']
        new_result_tuple = (infohash, seeders, new_result['leechers'], new_result['last_check'])

        if seeders > 0:
            self._torrents_checked[infohash] = new_result_tuple

    def on_torrent_health_check_completed(self, infohash, result):
        final_response = {}
        if not result or not isinstance(result, list):
            self._logger.info("Received invalid torrent checker result")
            self.notifier.notify(NTFY.CHANNEL_ENTITY_UPDATED,
                                 {"infohash": hexlify(infohash),
                                  "num_seeders": 0,
                                  "num_leechers": 0,
                                  "last_tracker_check": int(time.time()),
                                  "health": "updated"})
            return final_response

        torrent_update_dict = {'infohash': infohash, 'seeders': 0, 'leechers': 0, 'last_check': int(time.time())}
        for response in reversed(result):
            if isinstance(response, Exception):
                final_response[response.tracker_url] = {'error': str(response)}
                continue
            elif response is None:
                self._logger.warning("Torrent health response is none!")
                continue
            response_keys = list(response.keys())
            final_response[response_keys[0]] = response[response_keys[0]][0]

            s = response[response_keys[0]][0]['seeders']
            l = response[response_keys[0]][0]['leechers']

            # More leeches is better, because undefined peers are marked as leeches in DHT
            if s > torrent_update_dict['seeders'] or \
                    (s == torrent_update_dict['seeders'] and l > torrent_update_dict['leechers']):
                torrent_update_dict['seeders'] = s
                torrent_update_dict['leechers'] = l

        self._update_torrent_result(torrent_update_dict)
        self.update_torrents_checked(torrent_update_dict)

        # TODO: DRY! Stop doing lots of formats, just make REST endpoint automatically encode binary data to hex!
        self.notifier.notify(NTFY.CHANNEL_ENTITY_UPDATED,
                             {"infohash": hexlify(infohash),
                              "num_seeders": torrent_update_dict["seeders"],
                              "num_leechers": torrent_update_dict["leechers"],
                              "last_tracker_check": torrent_update_dict["last_check"],
                              "health": "updated"})
        return final_response

    @task
    async def check_torrent_health(self, infohash, timeout=20, scrape_now=False):
        """
        Check the health of a torrent with a given infohash.
        :param infohash: Torrent infohash.
        :param timeout: The timeout to use in the performed requests
        :param scrape_now: Flag whether we want to force scraping immediately
        """
        tracker_set = []

        # We first check whether the torrent is already in the database and checked before
        with db_session:
            result = self.mds.TorrentState.get(infohash=infohash)
            if result:
                torrent_id = result.infohash
                last_check = result.last_check
                time_diff = time.time() - last_check
                if time_diff < MIN_TORRENT_CHECK_INTERVAL and not scrape_now:
                    self._logger.debug("time interval too short, not doing torrent health check for %s",
                                       hexlify(infohash))
                    return {
                        "db": {
                            "seeders": result.seeders,
                            "leechers": result.leechers,
                            "infohash": hexlify(infohash)
                        }
                    }

                # get torrent's tracker list from DB
                tracker_set = self.get_valid_trackers_of_torrent(torrent_id)

        tasks = []
        for tracker_url in tracker_set:
            session = self._create_session_for_request(tracker_url, timeout=timeout)
            if session is None:
                return False
            session.add_infohash(infohash)
            tasks.append(self.connect_to_tracker(session))

        if has_bep33_support():
            # Create a (fake) DHT session for the lookup if we have support for BEP33.
            session = FakeBep33DHTSession(self.dlmgr, infohash, timeout)
        else:
            # Otherwise, fallback on the normal DHT metainfo lookups.
            session = FakeDHTSession(self.dlmgr, infohash, timeout)

        self._session_list['DHT'].append(session)
        tasks.append(self.connect_to_tracker(session))

        res = await gather(*tasks, return_exceptions=True)
        return self.on_torrent_health_check_completed(infohash, res)

    def _create_session_for_request(self, tracker_url, timeout=20):
        hops = self.config.download_defaults.number_hops
        if hops > len(self.socks_listen_ports or []):
            # Proxies never started, dropping the request
            return None
        proxy = ('127.0.0.1', self.socks_listen_ports[hops - 1]) if hops > 0 else None
        session = create_tracker_session(tracker_url, timeout, proxy, self.socket_mgr)

        if tracker_url not in self._session_list:
            self._session_list[tracker_url] = []
        self._session_list[tracker_url].append(session)

        self._logger.debug("Session created for tracker %s", tracker_url)
        return session

    async def clean_session(self, session):
        self.tracker_manager.update_tracker_info(session.tracker_url, not session.is_failed)
        # Remove the session from our session list dictionary
        self._session_list[session.tracker_url].remove(session)
        if len(self._session_list[session.tracker_url]) == 0 and session.tracker_url != "DHT":
            del self._session_list[session.tracker_url]

        await session.cleanup()

    async def _on_result_from_session(self, session, result_list):
        await self.clean_session(session)
        # FIXME: this should be probably handled by cancel, etc
        if self._should_stop:
            return

        return result_list

    def _update_torrent_result(self, response):
        infohash = response['infohash']
        seeders = response['seeders']
        leechers = response['leechers']
        last_check = response['last_check']

        self._logger.debug("Update result %s/%s for %s", seeders, leechers, hexlify(infohash))

        with db_session:
            # Update torrent state
            torrent = self.mds.TorrentState.get(infohash=infohash)
            if not torrent:
                self._logger.warning(
                    "Tried to update torrent health data in DB for an unknown torrent: %s", hexlify(infohash))
                return
            torrent.seeders = seeders
            torrent.leechers = leechers
            torrent.last_check = last_check
            torrent.self_checked = True
