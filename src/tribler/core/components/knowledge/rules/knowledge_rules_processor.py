import logging
import queue
import time
from dataclasses import dataclass
from datetime import timedelta
from typing import Optional, Set

import human_readable
from ipv8.taskmanager import TaskManager
from pony.orm import db_session

from tribler.core import notifications
from tribler.core.components.database.db.layers.knowledge_data_access_layer import ResourceType
from tribler.core.components.database.db.tribler_database import TriblerDatabase
from tribler.core.components.knowledge.rules.rules_content_items import content_items_rules
from tribler.core.components.knowledge.rules.rules_general_tags import general_rules
from tribler.core.components.knowledge.rules.tag_rules_base import extract_only_valid_tags
from tribler.core.components.metadata_store.db.serialization import REGULAR_TORRENT
from tribler.core.components.metadata_store.db.store import MetadataStore
from tribler.core.utilities.async_force_switch import force_switch
from tribler.core.utilities.notifier import Notifier
from tribler.core.utilities.unicode import hexlify

DEFAULT_BATCH_INTERVAL = 5
DEFAULT_BATCH_SIZE = 50

DEFAULT_QUEUE_INTERVAL = 5
DEFAULT_QUEUE_BATCH_SIZE = 100
DEFAULT_QUEUE_MAX_SIZE = 10000

LAST_PROCESSED_TORRENT_ID = 'last_processed_torrent_id'
RULES_PROCESSOR_VERSION = 'rules_processor_version'


@dataclass
class TorrentTitle:
    infohash: bytes
    title: str


class KnowledgeRulesProcessor(TaskManager):
    # this value must be incremented in the case of new rules set has been applied
    version: int = 5

    def __init__(self, notifier: Notifier, db: TriblerDatabase, mds: MetadataStore,
                 batch_size: int = DEFAULT_BATCH_SIZE, batch_interval: float = DEFAULT_BATCH_INTERVAL,
                 queue_interval: float = DEFAULT_QUEUE_INTERVAL, queue_batch_size: float = DEFAULT_QUEUE_BATCH_SIZE,
                 queue_max_size: int = DEFAULT_QUEUE_MAX_SIZE):
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

    def start(self):
        self.logger.info('Start')
        # The feature is suspended. See: https://github.com/Tribler/tribler/issues/7398#issuecomment-1772193981
        # self.start_batch_processing()
        self.start_queue_processing()

    async def shutdown(self):
        await self.shutdown_task_manager()

    def start_batch_processing(self):
        rules_processor_version = self.get_rules_processor_version()
        if rules_processor_version < self.version:
            # the database was processed by the previous version of the rules processor
            self.logger.info('New version of rules processor is available. Starting knowledge generation from scratch.')
            self.set_last_processed_torrent_id(0)
            self.set_rules_processor_version(self.version)

        max_row_id = self.mds.get_max_rowid()
        last_processed_torrent_id = self.get_last_processed_torrent_id()
        is_finished = last_processed_torrent_id >= max_row_id

        if not is_finished:
            self._start_rowid_in_current_session = last_processed_torrent_id
            self._start_time_in_current_session = time.time()
            self.logger.info(f'Register process_batch task with interval: {self.batch_interval} sec')
            self.register_task(
                name=self.process_batch.__name__,
                interval=self.batch_interval,
                task=self.process_batch
            )
        else:
            self.logger.info(f'Database processing is finished. Last processed torrent id: {max_row_id}')

    def start_queue_processing(self):
        # note that this notification can come from different threads
        self.notifier.add_observer(
            topic=notifications.new_torrent_metadata_created,
            observer=self.put_entity_to_the_queue,
            synchronous=True
        )
        self.logger.info(f'Register process_queue task with interval: {self.queue_interval} sec')
        # register the task with a delay to prevent simultaneous calls for batch processing and queue processing.
        self.register_task(
            name=self.process_queue.__name__,
            delay=self.queue_interval / 2,
            interval=self.queue_interval, task=self.process_queue
        )

    async def process_batch(self) -> int:
        def query(_start, _end):
            return lambda t: _start < t.rowid and t.rowid <= _end and \
                             t.metadata_type == REGULAR_TORRENT and \
                             t.tag_processor_version < self.version

        start = self.get_last_processed_torrent_id()
        max_row_id = self.mds.get_max_rowid()
        end = min(start + self.batch_size, max_row_id)
        start_time = time.time()

        self.logger.info(f'Processing batch [{start}...{end}]')

        with db_session:
            batch = list(self.mds.TorrentMetadata.select(query(start, end)))
        self.logger.info(f'Query duration: {(time.time() - start_time):.3f} seconds.')

        processed = 0
        added = 0
        start_time = time.time()

        for torrent in batch:
            added += await self.process_torrent_title(torrent.infohash, torrent.title)
            processed += 1

        self.set_last_processed_torrent_id(end)

        duration = time.time() - start_time

        def calculate_eta():
            processed_in_the_current_session = end - self._start_rowid_in_current_session
            remaining = max_row_id - end
            duration_in_the_current_session = time.time() - self._start_time_in_current_session
            eta = remaining * duration_in_the_current_session / processed_in_the_current_session
            return f'{human_readable.time_delta(timedelta(seconds=eta))} ({remaining} torrents left)'

        message = f'[Batch] Processed: {processed} titles. Added: {added} statements. Duration: {duration:.3f} ' \
                  f'seconds. Estimated time for full processing: {calculate_eta()}'
        self.logger.info(message)

        is_finished = end >= max_row_id
        if is_finished:
            self.logger.info('Finish batch processing, cancel process_batch task')
            self.cancel_pending_task(name=self.process_batch.__name__)
        return processed

    async def process_queue(self) -> int:
        processed = 0
        added = 0
        start_time = time.time()

        try:
            while title := self.queue.get_nowait():
                added += await self.process_torrent_title(title.infohash, title.title)
                processed += 1

                if processed >= self.queue_batch_size:
                    break  # limit the number of processed items to prevent long processing
        except queue.Empty:
            pass

        if processed:
            duration = time.time() - start_time
            message = f'[Queue] Processed: {processed} titles. Added: {added} tags. Duration: {duration:.3f} seconds.'
            self.logger.info(message)
        return processed

    def put_entity_to_the_queue(self, infohash: Optional[bytes] = None, title: Optional[str] = None):
        """ Put entity to the queue to be processed by the rules processor.
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

    @force_switch
    async def process_torrent_title(self, infohash: Optional[bytes] = None, title: Optional[str] = None) -> int:
        if not infohash or not title:
            return 0
        infohash_str = hexlify(infohash)

        # The feature is suspended. See: https://github.com/Tribler/tribler/issues/7398#issuecomment-1772193981
        # self.save_statements(subject_type=ResourceType.TORRENT, subject=infohash_str, predicate=ResourceType.TITLE,
        #                      objects={title})

        if tags := set(extract_only_valid_tags(title, rules=general_rules)):
            self.save_statements(subject_type=ResourceType.TORRENT, subject=infohash_str, predicate=ResourceType.TAG,
                                 objects=tags)

        if content_items := set(extract_only_valid_tags(title, rules=content_items_rules)):
            self.save_statements(subject_type=ResourceType.TORRENT, subject=infohash_str,
                                 predicate=ResourceType.CONTENT_ITEM, objects=content_items)

        return len(tags) + len(content_items) + 1

    @db_session
    def save_statements(self, subject_type: ResourceType, subject: str, predicate: ResourceType, objects: Set[str]):
        self.logger.debug(f'Save: {len(objects)} objects for "{subject}" with predicate={predicate}')
        for obj in objects:
            self.db.knowledge.add_auto_generated_operation(subject_type=subject_type, subject=subject,
                                                           predicate=predicate, obj=obj)

    @db_session
    def get_last_processed_torrent_id(self) -> int:
        return int(self.db.get_misc(LAST_PROCESSED_TORRENT_ID, default='0'))

    @db_session
    def set_last_processed_torrent_id(self, value: int):
        self.db.set_misc(LAST_PROCESSED_TORRENT_ID, str(value))

    @db_session
    def get_rules_processor_version(self) -> int:
        return int(self.db.get_misc(RULES_PROCESSOR_VERSION, default='0'))

    @db_session
    def set_rules_processor_version(self, version: int):
        self.db.set_misc(RULES_PROCESSOR_VERSION, str(version))
