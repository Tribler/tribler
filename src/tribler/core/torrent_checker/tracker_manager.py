from __future__ import annotations

import logging
import time
from pathlib import Path
from typing import TYPE_CHECKING

from pony.orm import count, db_session

from tribler.core.libtorrent.trackers import get_uniformed_tracker_url

if TYPE_CHECKING:
    from tribler.core.database.store import MetadataStore

MAX_TRACKER_FAILURES = 5  # if a tracker fails this amount of times in a row, its 'is_alive' will be marked as 0 (dead).
TRACKER_RETRY_INTERVAL = 60  # A "dead" tracker will be retired every 60 seconds


class TrackerManager:
    """
    A manager for tracker info in the database.
    """

    def __init__(self, state_dir: Path | None = None, metadata_store: MetadataStore = None) -> None:
        """
        Create a new tracker manager.
        """
        self._logger = logging.getLogger(self.__class__.__name__)
        self.state_dir = state_dir
        self.TrackerState = metadata_store.TrackerState

        self.blacklist: list[str] = []
        self.load_blacklist()

    def load_blacklist(self) -> None:
        """
        Load the tracker blacklist from tracker_blacklist.txt in the session state directory.

        Entries are newline separated and are supposed to be sanitized.
        """
        blacklist_file = (Path(self.state_dir or ".") / "tracker_blacklist.txt").absolute()
        if blacklist_file.exists():
            with open(blacklist_file) as blacklist_file_handle:
                # Note that get_uniformed_tracker_url will strip the newline at the end of .readlines()
                self.blacklist.extend([get_uniformed_tracker_url(url) for url in blacklist_file_handle.readlines()])
        else:
            self._logger.info("No tracker blacklist file found at %s.", blacklist_file)

    def get_tracker_info(self, tracker_url: str) -> dict[str, str | float] | None:
        """
        Gets the tracker information with the given tracker URL.

        :param tracker_url: The given tracker URL.
        :return: The tracker info dict if exists, None otherwise.
        """
        sanitized_tracker_url = get_uniformed_tracker_url(tracker_url) if tracker_url != "DHT" else tracker_url

        with db_session:
            tracker = list(self.TrackerState.select(lambda g: g.url == sanitized_tracker_url))
            if tracker:
                return {
                    "id": tracker[0].url,
                    "last_check": tracker[0].last_check,
                    "failures": tracker[0].failures,
                    "is_alive": tracker[0].alive
                }
            return None

    def add_tracker(self, tracker_url: str) -> None:
        """
        Adds a new tracker into the tracker info dict and the database.

        :param tracker_url: The new tracker URL to be added.
        """
        sanitized_tracker_url = get_uniformed_tracker_url(tracker_url)
        if sanitized_tracker_url is None:
            self._logger.warning("skip invalid tracker: %s", repr(tracker_url))
            return

        with db_session:
            num = count(g for g in self.TrackerState if g.url == sanitized_tracker_url)
            if num > 0:
                self._logger.debug("skip existing tracker: %s", repr(tracker_url))
                return

            # insert into database
            self.TrackerState(url=sanitized_tracker_url,
                              last_check=0,
                              failures=0,
                              alive=True,
                              torrents={})

    def remove_tracker(self, tracker_url: str) -> None:
        """
        Remove a given tracker from the database.
        URL is sanitized first and removed from the database. If the URL is ill formed then try removing the non-
        sanitized version.

        :param tracker_url: The URL of the tracker to be deleted.
        """
        sanitized_tracker_url = get_uniformed_tracker_url(tracker_url)

        with db_session:
            options = self.TrackerState.select(lambda g: g.url in [tracker_url, sanitized_tracker_url])
            for option in options[:]:
                option.delete()

    @db_session
    def update_tracker_info(self, tracker_url: str, is_successful: bool = True) -> None:
        """
        Updates a tracker information.

        :param tracker_url: The given tracker_url.
        :param is_successful: If the check was successful.
        """
        if tracker_url == "DHT":
            return

        sanitized_tracker_url = get_uniformed_tracker_url(tracker_url)
        tracker = self.TrackerState.get(lambda g: g.url == sanitized_tracker_url)

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
        self._logger.info("Tracker updated: %s. Alive: %s. Failures: %d.", tracker.url, str(is_alive), failures)

    @db_session
    def get_next_tracker(self) -> str | None:
        """
        Gets the next tracker.

        :return: The next tracker for torrent-checking.
        """
        tracker = self.TrackerState.select(
            lambda g: str(g.url)
                      and g.alive
                      and g.last_check + TRACKER_RETRY_INTERVAL <= int(time.time())
                      and str(g.url) not in self.blacklist
        ).order_by(self.TrackerState.last_check).limit(1)
        if not tracker:
            return None
        return tracker[0]
