import logging
import random
import time
from typing import Optional, Dict

from pony.orm import db_session, desc, select
from pony.utils import between

from tribler.core import notifications
from tribler.core.components.libtorrent.download_manager.download_manager import DownloadManager
from tribler.core.components.metadata_store.db.serialization import REGULAR_TORRENT
from tribler.core.components.metadata_store.db.store import MetadataStore
from tribler.core.components.torrent_checker.torrent_checker.dataclasses import HEALTH_FRESHNESS_SECONDS, HealthInfo
from tribler.core.components.torrent_checker.torrent_checker.tracker_manager import TrackerManager, MAX_TRACKER_FAILURES
from tribler.core.utilities.notifier import Notifier
from tribler.core.utilities.unicode import hexlify
from tribler.core.utilities.utilities import is_valid_url

MIN_TORRENT_CHECK_INTERVAL = 900  # How much time we should wait before checking a torrent again
TORRENT_CHECK_RETRY_INTERVAL = 30  # Interval when the torrent was successfully checked for the last time
MAX_TORRENTS_CHECKED_PER_SESSION = 50

TORRENT_SELECTION_POOL_SIZE = 2  # How many torrents to check (popular or random) during periodic check
USER_CHANNEL_TORRENT_SELECTION_POOL_SIZE = 5  # How many torrents to check from user's channel during periodic check
TORRENTS_CHECKED_RETURN_SIZE = 240  # Estimated torrents checked on default 4 hours idle run


class DbService:

    def __init__(self,
                 download_manager: DownloadManager,
                 tracker_manager: TrackerManager,
                 metadata_store: MetadataStore,
                 notifier: Notifier,):
        super().__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self.tracker_manager = tracker_manager
        self.mds = metadata_store
        self.download_manager = download_manager
        self.notifier = notifier

        # We keep track of the results of popular torrents checked by you.
        # The popularity community gossips this information around.
        self._torrents_checked: Optional[Dict[bytes, HealthInfo]] = None

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

    def get_next_tracker_and_infohashes(self):
        tracker = self.get_next_tracker()
        if not tracker:
            return None, None

        # get the torrents that should be checked
        url = tracker.url
        with db_session:
            dynamic_interval = TORRENT_CHECK_RETRY_INTERVAL * (2 ** tracker.failures)
            torrents = select(ts for ts in tracker.torrents if ts.last_check + dynamic_interval < int(time.time()))
            infohashes = [t.infohash for t in torrents[:MAX_TORRENTS_CHECKED_PER_SESSION]]

        return url, infohashes

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

    def is_blacklisted_tracker(self, tracker_url):
        return tracker_url in self.tracker_manager.blacklist

    @db_session
    def get_valid_trackers_of_torrent(self, infohash):
        """ Get a set of valid trackers for torrent. Also remove any invalid torrent."""
        db_tracker_list = self.mds.TorrentState.get(infohash=infohash).trackers
        return {tracker.url for tracker in db_tracker_list
                if is_valid_url(tracker.url) and not self.is_blacklisted_tracker(tracker.url)}

    @db_session
    def get_recent_health_result_if_exists(self, infohash):
        torrent_state = self.mds.TorrentState.get(infohash=infohash)
        if torrent_state:
            last_check = torrent_state.last_check
            time_diff = time.time() - last_check
            if time_diff < MIN_TORRENT_CHECK_INTERVAL:
                return torrent_state.to_health()

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
