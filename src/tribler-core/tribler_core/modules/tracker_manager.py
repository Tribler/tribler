import logging
import time

from pony.orm import count, db_session

from tribler_core.utilities import path_util
from tribler_core.utilities.tracker_utils import get_uniformed_tracker_url

MAX_TRACKER_FAILURES = 5  # if a tracker fails this amount of times in a row, its 'is_alive' will be marked as 0 (dead).
TRACKER_RETRY_INTERVAL = 60    # A "dead" tracker will be retired every 60 seconds


class TrackerManager:

    def __init__(self, session):
        self._logger = logging.getLogger(self.__class__.__name__)
        self._session = session

        self.blacklist = []
        self.load_blacklist()

    @property
    def tracker_store(self):
        return self._session.mds.TrackerState

    def load_blacklist(self):
        """
        Load the tracker blacklist from tracker_blacklist.txt in the session state directory.

        Entries are newline separated and are supposed to be sanitized.
        """
        blacklist_file = path_util.abspath(self._session.config.get_state_dir() / "tracker_blacklist.txt")
        if blacklist_file.exists():
            with open(blacklist_file) as blacklist_file_handle:
                # Note that get_uniformed_tracker_url will strip the newline at the end of .readlines()
                self.blacklist.extend([get_uniformed_tracker_url(url) for url in blacklist_file_handle.readlines()])
        else:
            self._logger.info("No tracker blacklist file found at %s.", blacklist_file)

    def get_tracker_info(self, tracker_url):
        """
        Gets the tracker information with the given tracker URL.
        :param tracker_url: The given tracker URL.
        :return: The tracker info dict if exists, None otherwise.
        """
        sanitized_tracker_url = get_uniformed_tracker_url(tracker_url) if tracker_url != "DHT" else tracker_url

        with db_session:
            tracker = list(self.tracker_store.select(lambda g: g.url == sanitized_tracker_url))
            if tracker:
                return {
                    'id': tracker[0].url,
                    'last_check': tracker[0].last_check,
                    'failures': tracker[0].failures,
                    'is_alive': tracker[0].alive
                }
            return None

    def add_tracker(self, tracker_url):
        """
        Adds a new tracker into the tracker info dict and the database.
        :param tracker_url: The new tracker URL to be added.
        """
        sanitized_tracker_url = get_uniformed_tracker_url(tracker_url)
        if sanitized_tracker_url is None:
            self._logger.warning("skip invalid tracker: %s", repr(tracker_url))
            return

        with db_session:
            num = count(g for g in self.tracker_store if g.url == sanitized_tracker_url)
            if num > 0:
                self._logger.debug("skip existing tracker: %s", repr(tracker_url))
                return

            # insert into database
            self.tracker_store(url=sanitized_tracker_url,
                               last_check=0,
                               failures=0,
                               alive=True,
                               torrents={})

    def remove_tracker(self, tracker_url):
        """
        Remove a given tracker from the database.
        URL is sanitized first and removed from the database. If the URL is ill formed then try removing the non-
        sanitized version.
        :param tracker_url: The URL of the tracker to be deleted.
        """
        sanitized_tracker_url = get_uniformed_tracker_url(tracker_url)

        with db_session:
            options = self.tracker_store.select(lambda g: g.url in [tracker_url, sanitized_tracker_url])
            for option in options[:]:
                option.delete()

    @db_session
    def update_tracker_info(self, tracker_url, is_successful):
        """
        Updates a tracker information.
        :param tracker_url: The given tracker_url.
        :param is_successful: If the check was successful.
        """

        if tracker_url == "DHT":
            return

        sanitized_tracker_url = get_uniformed_tracker_url(tracker_url)
        tracker = self.tracker_store.get(lambda g: g.url == sanitized_tracker_url)

        if not tracker:
            self._logger.error("Trying to update the tracker info of an unknown tracker URL")
            return

        current_time = int(time.time())
        failures = 0 if is_successful else tracker.failures + 1
        is_alive = failures < MAX_TRACKER_FAILURES

        # update the dict
        tracker.last_check = current_time
        tracker.failures = failures
        tracker.alive = is_alive

    @db_session
    def get_next_tracker_for_auto_check(self):
        """
        Gets the next tracker for automatic tracker-checking.
        :return: The next tracker for automatic tracker-checking.
        """
        tracker = self.tracker_store.select(lambda g: str(g.url)
                                            and g.alive
                                            and g.last_check + TRACKER_RETRY_INTERVAL <= int(time.time())
                                            and str(g.url) not in self.blacklist)\
            .order_by(self.tracker_store.last_check).limit(1)

        if not tracker:
            return None
        return tracker[0]
