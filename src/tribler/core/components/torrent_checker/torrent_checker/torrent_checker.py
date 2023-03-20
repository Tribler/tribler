import logging
import time
from asyncio import CancelledError
from typing import Dict, List, Optional, Tuple, Union

from ipv8.taskmanager import TaskManager

from tribler.core.components.libtorrent.download_manager.download_manager import DownloadManager
from tribler.core.components.metadata_store.db.store import MetadataStore
from tribler.core.components.torrent_checker.torrent_checker.checker_service import CheckerService
from tribler.core.components.torrent_checker.torrent_checker.dataclasses import HealthInfo
from tribler.core.components.torrent_checker.torrent_checker.db_service import DbService
from tribler.core.components.torrent_checker.torrent_checker.tracker_manager import TrackerManager
from tribler.core.components.torrent_checker.torrent_checker.utils import gather_coros
from tribler.core.config.tribler_config import TriblerConfig
from tribler.core.utilities.notifier import Notifier
from tribler.core.utilities.tracker_utils import MalformedTrackerURLException
from tribler.core.utilities.unicode import hexlify

TRACKER_SELECTION_INTERVAL = 1  # The interval for querying a random tracker
TORRENT_SELECTION_INTERVAL = 120  # The interval for checking the health of a random torrent
USER_CHANNEL_TORRENT_SELECTION_INTERVAL = 10 * 60  # The interval for checking the health of torrents in user's channel.


class TorrentChecker(TaskManager):
    def __init__(self,
                 config: TriblerConfig,
                 download_manager: DownloadManager,
                 notifier: Notifier,
                 tracker_manager: TrackerManager,
                 metadata_store: MetadataStore,
                 socks_proxy: Optional[Tuple[str, int]] = None):
        super().__init__()
        self._logger = logging.getLogger(self.__class__.__name__)
        self.tracker_manager = tracker_manager
        self.mds = metadata_store
        self.download_manager = download_manager
        self.notifier = notifier
        self.config = config

        self.db_service = DbService(download_manager, tracker_manager, metadata_store, notifier)
        self.checker_service = CheckerService(download_manager, socks_proxy)

    async def initialize(self):
        self.register_task("check random tracker", self.check_random_tracker, interval=TRACKER_SELECTION_INTERVAL)
        self.register_task("check local torrents", self.check_local_torrents, interval=TORRENT_SELECTION_INTERVAL)
        self.register_task("check channel torrents", self.check_torrents_in_user_channel,
                           interval=USER_CHANNEL_TORRENT_SELECTION_INTERVAL)

        await self.checker_service.initialize()

    async def shutdown(self):
        """
        Shutdown the torrent health checker.
        Once shut down it can't be started again.
        :returns A deferred that will fire once the shutdown has completed.
        """
        await self.checker_service.shutdown()
        await self.shutdown_task_manager()

    async def check_random_tracker(self):
        """
        Calling this method will fetch a random tracker from the database, select some torrents that have this
        tracker, and perform a request to these trackers.
        Return whether the check was successful.
        """
        if self.checker_service.should_stop():
            self._logger.warning("Not performing tracker check since we are shutting down")
            return

        url, infohashes = self.db_service.get_next_tracker_and_infohashes()
        if not url:
            self._logger.warning("No tracker to select from to check torrent health, skip")
            return

        if not infohashes:
            # We have no torrent to recheck for this tracker. Still update the last_check for this tracker.
            self._logger.info(f"No torrent to check for tracker {url}")
            self.tracker_manager.update_tracker_info(url)
            return

        self._logger.info(f"Selected {len(infohashes)} new torrents to check on random tracker: {url}")
        try:
            response = await self.checker_service.check_tracker_with_infohashes(url, infohashes)

            health_list = response.torrent_health_list
            self._logger.info(f"Received {len(health_list)} health info results from tracker: {url}")

            for health in health_list:
                self.db_service.update_torrent_health(health)

            self.tracker_manager.update_tracker_info(url, True)

        except MalformedTrackerURLException as e:
            self.tracker_manager.remove_tracker(url)
            self._logger.warning(e)

        except CancelledError:
            self._logger.info(f"Tracker session is being cancelled: {url}")
            raise

        except Exception as e:  # pylint: disable=broad-except
            self.tracker_manager.update_tracker_info(url, False)
            self._logger.warning(e)

    @property
    def torrents_checked(self) -> Dict[bytes, HealthInfo]:
        return self.db_service.torrents_checked

    async def check_local_torrents(self) -> Tuple[List, List]:
        """
        Perform a full health check on a few popular and old torrents in the database.
        """
        selected_torrents = self.db_service.torrents_to_check()
        self._logger.info(f'Check {len(selected_torrents)} local torrents')
        coros = [self.check_torrent_health(t.infohash) for t in selected_torrents]
        results = await gather_coros(coros)
        self._logger.info(f'Results for local torrents check: {results}')
        return selected_torrents, results

    async def check_torrents_in_user_channel(self) -> List[Union[HealthInfo, BaseException]]:
        """
        Perform a full health check of torrents in user's channel
        """
        selected_torrents = self.db_service.torrents_to_check_in_user_channel()
        self._logger.info(f'Check {len(selected_torrents)} torrents in user channel')
        coros = [self.check_torrent_health(t.infohash) for t in selected_torrents]
        results = await gather_coros(coros)
        self._logger.info(f'Results for torrents in user channel: {results}')
        return results

    async def check_torrent_health(self, infohash: bytes, timeout=20, scrape_now=False) -> HealthInfo:
        """
        Check the health of a torrent with a given infohash.
        :param infohash: Torrent infohash.
        :param timeout: The timeout to use in the performed requests
        :param scrape_now: Flag whether we want to force scraping immediately
        """
        infohash_hex = hexlify(infohash)
        self._logger.info(f'Check health for the torrent: {infohash_hex}')

        if not scrape_now:
            health_info = self.db_service.get_recent_health_result_if_exists(infohash)
            if health_info:
                return health_info

        # get torrent's tracker list from DB
        tracker_set = self.db_service.get_valid_trackers_of_torrent(infohash)
        self._logger.info(f'Trackers for {infohash_hex}: {tracker_set}')

        health = await self.checker_service.check_torrent_health(infohash, tracker_set, timeout=timeout)
        if health.last_check == 0:  # if not zero, was already updated in get_tracker_response
            health.last_check = int(time.time())
            health.self_checked = True
            self.db_service.update_torrent_health(health)
