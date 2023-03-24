import logging
import time
from asyncio import CancelledError
from typing import Dict, List, Optional, Tuple, Union

from ipv8.taskmanager import TaskManager

from tribler.core import notifications
from tribler.core.components.libtorrent.download_manager.download_manager import DownloadManager
from tribler.core.components.metadata_store.db.store import MetadataStore
# from tribler.core.components.torrent_checker.torrent_checker.checker_service import CheckerService
from tribler.core.components.torrent_checker.torrent_checker.dataclasses import HealthInfo
from tribler.core.components.torrent_checker.torrent_checker.db_service import DbService
from tribler.core.components.torrent_checker.torrent_checker.checker_service import CheckerService
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
    """
    Torrent Checker is built as module responsible for checking the health (i.e. seeders, leechers, last check date)
    of torrents using the available trackers and saving that health info in the database for quick retrieval later.
    Therefore, it consists of the two services.
    1. Checker Service
    2. Database Service

    Checker Service is a stateless service that primarily checks the health of a given torrent using the provided
    trackers. If no trackers are provided, DHT is used. The supported trackers are HTTP(S) and UDP trackers.

    Database Service is a persistence service that primarily saves the health info received from the Checker Service
    when a torrent health is checked and returns the info when accessed. If the health info returned from the database
    is recent enough (check MIN_TORRENT_CHECK_INTERVAL seconds in Database Service module), it is returned as the
    current health info instead of actually checking using the trackers by Checker Service.

    Besides the Checker Service and Database Service, Torrent Checker is also responsible for doing periodic checks of
    the following:
    1. Local Torrents : Local torrents are the torrents available in the database. Some popular (indicated by high
                        number of seeders) and old torrents (based on last check date) are periodically checked.
    2. Channel Torrents : The torrents on the user's channels are also periodically checked to make sure the health info
                        on the channel torrents remains up-to-date.
    3. Random Tracker : Periodically a random tracker and the torrents (infohash) associated with it are selected to do
                        the tracker check. With tracker check, when the response is received from the tracker for those
                        infohashes, the health info is updated on the database.
    """
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
        self.checker_service = CheckerService(proxy=socks_proxy)

    async def initialize(self):
        """
        Initializes the torrent checker.

        First the health checker is initialized before periodic tasks. This is because these periodics tasks
        depend on checker service which should be ready to respond to health check requests.
        """
        await self.checker_service.initialize()

        self.register_task("check random tracker", self.check_random_tracker, interval=TRACKER_SELECTION_INTERVAL)
        self.register_task("check local torrents", self.check_local_torrents, interval=TORRENT_SELECTION_INTERVAL)
        self.register_task("check channel torrents", self.check_torrents_in_user_channel,
                           interval=USER_CHANNEL_TORRENT_SELECTION_INTERVAL)

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
        This is one of the periodic task that fetches a random tracker and associated torrents from the database
        service and performs a tracker check request using the checker service. The response is then saved in the
        database. Additionally, it also updates that status of the tracker as alive or not. Non-proper trackers are
        removed.
        """
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
            response = await self.checker_service.get_tracker_response(url, infohashes)

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

    async def check_local_torrents(self) -> List[Union[HealthInfo, BaseException]]:
        """
        This is one of the periodic that fetches some popular (indicated by high number of seeders) and
        old torrents (based on last check date) and checks them using Checker Service. The results are then
        saved to the database.
        """
        selected_torrents = self.db_service.torrents_to_check()
        self._logger.info(f'Initiating check on {len(selected_torrents)} local torrents')

        infohashes = [t.infohash for t in selected_torrents]
        results = await self.check_multiple_torrents_health(infohashes)
        self._logger.info(f'Check completed for {len(results)} local torrents')

        return results

    async def check_torrents_in_user_channel(self) -> List[Union[HealthInfo, BaseException]]:
        """
        This is one of the periodic tasks that fetches the torrents on the user's channels and checks them
        using Checker Service. The results are then saved to the database. This makes sure that the health info
        on the channel torrents remains up-to-date.
        """
        selected_torrents = self.db_service.torrents_to_check_in_user_channel()
        self._logger.info(f'Initiating check on {len(selected_torrents)} torrents in user channel')

        infohashes = [t.infohash for t in selected_torrents]
        results = await self.check_multiple_torrents_health(infohashes)
        self._logger.info(f'Check completed for {len(results)} torrents in user channel')

        return results

    async def check_multiple_torrents_health(self, infohashes: List[bytes]):
        coros = [self.check_torrent_health(infohash) for infohash in infohashes]
        results = await gather_coros(coros)
        return results

    async def check_torrent_health(self, infohash: bytes, timeout=20, scrape_now=False) -> HealthInfo:
        """
        Checks the health of a torrent with a given infohash. If a recent health info is found in the database,
        it is returned as is. Otherwise, Checker Service is used to check the torrent health with available trackers.

        :param infohash: Torrent infohash (bytes).
        :param timeout: The timeout to use in the performed requests.
        :param scrape_now: Flag whether we want to force scraping immediately.
        """
        infohash_hex = hexlify(infohash)
        self._logger.info(f'Check health for the torrent: {infohash_hex}')

        if not scrape_now:
            health_info = self.db_service.get_recent_health_result_if_exists(infohash)
            if health_info:
                return health_info

        tracker_set = self.db_service.get_valid_trackers_of_torrent(infohash)
        self._logger.info(f'Trackers for {infohash_hex}: {tracker_set}')

        health = await self.checker_service.get_health_info(infohash, trackers=tracker_set, timeout=timeout)
        self.db_service.update_torrent_health(health)

        self.notify(health)
        return health

    def notify(self, health: HealthInfo):
        """
        The health check is usually triggered from the GUI side in which case we'll have to update the GUI
        when the health info is available. This is done simply by calling the notifier.
        """
        self.notifier[notifications.channel_entity_updated]({
            'infohash': health.infohash_hex,
            'num_seeders': health.seeders,
            'num_leechers': health.leechers,
            'last_tracker_check': health.last_check,
            'health': 'updated'
        })
