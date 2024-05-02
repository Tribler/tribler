from __future__ import annotations

import logging
import queue
import time
from binascii import hexlify
from dataclasses import dataclass
from typing import TYPE_CHECKING

from ipv8.taskmanager import TaskManager
from pony.orm import db_session

from tribler.core.database.layers.knowledge import ResourceType
from tribler.core.knowledge.rules.rules import content_items_rules, extract_only_valid_tags, general_rules
from tribler.core.notifier import Notification, Notifier

if TYPE_CHECKING:
    from tribler.core.database.store import MetadataStore
    from tribler.core.database.tribler_database import TriblerDatabase

DEFAULT_BATCH_INTERVAL = 5
DEFAULT_BATCH_SIZE = 50

DEFAULT_QUEUE_INTERVAL = 5
DEFAULT_QUEUE_BATCH_SIZE = 100
DEFAULT_QUEUE_MAX_SIZE = 10000

LAST_PROCESSED_TORRENT_ID = "last_processed_torrent_id"
RULES_PROCESSOR_VERSION = "rules_processor_version"


@dataclass
class TorrentTitle:
    """
    A container for infohashes with names.
    """

    infohash: bytes
    title: str


class KnowledgeRulesProcessor(TaskManager):
    """
    Periodically extract tags from database entries.
    """

    version: int = 5  # this value must be incremented in the case of new rules set has been applied

    def __init__(self, notifier: Notifier, db: TriblerDatabase, mds: MetadataStore,  # noqa: PLR0913
                 batch_size: int = DEFAULT_BATCH_SIZE, batch_interval: float = DEFAULT_BATCH_INTERVAL,
                 queue_interval: float = DEFAULT_QUEUE_INTERVAL, queue_batch_size: float = DEFAULT_QUEUE_BATCH_SIZE,
                 queue_max_size: int = DEFAULT_QUEUE_MAX_SIZE) -> None:
        """
        Default values for batch_size and interval are chosen so that tag processing is not too heavy
        fot CPU and with this values 36000 items will be processed within the hour.
        1M items will be processed withing 28 hours.
        """
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)

        self.notifier = notifier
        self.db = db
        self.mds = mds
        self.batch_size = batch_size
        self.batch_interval = batch_interval
        self.queue_interval = queue_interval
        self.queue_batch_size = queue_batch_size
        self.queue_max_size = queue_max_size

        self._last_warning_time = 0
        self._start_rowid_in_current_session = 0
        self._start_time_in_current_session = 0

        # this queue is used to be able to process entities supplied from another thread.
        self.queue: queue.Queue[TorrentTitle] = queue.Queue(maxsize=self.queue_max_size)

    def start(self) -> None:
        """
        Start processing.
        """
        self.logger.info("Start")

        # note that this notification can come from different threads
        self.notifier.add(Notification.new_torrent_metadata_created, self.put_entity_to_the_queue)
        self.logger.info("Register process_queue task with interval: %f sec", self.queue_interval)

        # register the task with a delay to prevent simultaneous calls for batch processing and queue processing.
        self.register_task(self.process_queue.__name__, self.process_queue, delay=self.queue_interval / 2,
                           interval=self.queue_interval)

    async def process_queue(self) -> int:
        """
        Process the queue of pending torrent titles to extract tags from.
        """
        processed = 0
        added = 0
        start_time = time.time()

        try:
            while title := self.queue.get_nowait():
                added += self.process_torrent_title(title.infohash, title.title)
                processed += 1

                if processed >= self.queue_batch_size:
                    break  # limit the number of processed items to prevent long processing
        except queue.Empty:
            pass

        if processed:
            self.logger.info("[Queue] Processed: %d titles. Added: %d tags. Duration: %f seconds.",
                             processed, added, round(time.time() - start_time, 3))
        return processed

    def put_entity_to_the_queue(self, infohash: bytes | None = None, title: str | None = None) -> None:
        """
        Put entity to the queue to be processed by the rules processor.
        This method is prepared for use from a different thread.
        """
        if not infohash or not title:
            return
        try:
            self.queue.put_nowait(TorrentTitle(infohash, title))
        except queue.Full:
            now = time.time()
            time_passed = now - self._last_warning_time
            if time_passed > 5:  # sec
                self.logger.warning('Queue is full')
                self._last_warning_time = now

    def process_torrent_title(self, infohash: bytes | None = None, title: str | None = None) -> int:
        """
        Extract tags from a title and save the statements.

        :returns: The number of new titles and content items.
        """
        if not infohash or not title:
            return 0
        infohash_str = hexlify(infohash).decode()

        if tags := set(extract_only_valid_tags(title, rules=general_rules)):
            self.save_statements(subject_type=ResourceType.TORRENT, subject=infohash_str, predicate=ResourceType.TAG,
                                 objects=tags)

        if content_items := set(extract_only_valid_tags(title, rules=content_items_rules)):
            self.save_statements(subject_type=ResourceType.TORRENT, subject=infohash_str,
                                 predicate=ResourceType.CONTENT_ITEM, objects=content_items)

        return len(tags) + len(content_items) + 1

    @db_session
    def save_statements(self, subject_type: ResourceType, subject: str,
                        predicate: ResourceType, objects: set[str]) -> None:
        """
        Store teh given statements in the database.
        """
        self.logger.debug("Save: %d objects for \"%s\" with predicate=%s", len(objects), str(subject), str(predicate))
        for obj in objects:
            self.db.knowledge.add_auto_generated_operation(subject_type=subject_type, subject=subject,
                                                           predicate=predicate, obj=obj)

    @db_session
    def get_last_processed_torrent_id(self) -> int:
        """
        Retrieve the database index of the last inserted torrent.
        """
        return int(self.db.get_misc(LAST_PROCESSED_TORRENT_ID, default="0"))

    @db_session
    def set_last_processed_torrent_id(self, value: int) -> None:
        """
        Set the database index of the last inserted torrent.
        """
        self.db.set_misc(LAST_PROCESSED_TORRENT_ID, str(value))

    @db_session
    def get_rules_processor_version(self) -> int:
        """
        Get the version number of the database.
        """
        return int(self.db.get_misc(RULES_PROCESSOR_VERSION, default="0"))

    @db_session
    def set_rules_processor_version(self, version: int) -> None:
        """
        Set the version number of the database.
        """
        self.db.set_misc(RULES_PROCESSOR_VERSION, str(version))
