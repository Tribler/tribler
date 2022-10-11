import logging
from typing import Optional, Set

from ipv8.taskmanager import TaskManager
from pony.orm import db_session

from tribler.core import notifications
from tribler.core.components.metadata_store.db.serialization import REGULAR_TORRENT
from tribler.core.components.metadata_store.db.store import MetadataStore
from tribler.core.components.tag.db.tag_db import ResourceType, TagDatabase
from tribler.core.components.tag.rules.rules_content_items import content_items_rules
from tribler.core.components.tag.rules.rules_general_tags import general_rules
from tribler.core.components.tag.rules.tag_rules_base import extract_only_valid_tags
from tribler.core.utilities.notifier import Notifier
from tribler.core.utilities.unicode import hexlify

DEFAULT_INTERVAL = 10
DEFAULT_BATCH_SIZE = 1000

LAST_PROCESSED_TORRENT_ID = 'last_processed_torrent_id'


class TagRulesProcessor(TaskManager):
    # this value must be incremented in the case of new rules set has been applied
    version: int = 2

    def __init__(self, notifier: Notifier, db: TagDatabase, mds: MetadataStore,
                 batch_size: int = DEFAULT_BATCH_SIZE, interval: float = DEFAULT_INTERVAL):
        """
        Default values for batch_size and interval are chosen so that tag processing is not too heavy
        fot CPU and with this values 360k items will be processed within the hour.
        """
        super().__init__()
        self.logger = logging.getLogger(self.__class__.__name__)

        self.notifier = notifier
        self.db = db
        self.mds = mds
        self.batch_size = batch_size
        self.interval = interval
        self.notifier.add_observer(notifications.new_torrent_metadata_created, self.process_torrent_title,
                                   synchronous=True)

    @db_session
    def start(self):
        self.logger.info('Start')

        max_row_id = self.mds.get_max_rowid()
        is_finished = self.get_last_processed_torrent_id() >= max_row_id

        if not is_finished:
            self.logger.info(f'Register process_batch task with interval: {self.interval} sec')
            self.register_task(name=self.process_batch.__name__,
                               interval=self.interval,
                               task=self.process_batch)

    async def shutdown(self):
        await self.shutdown_task_manager()

    @db_session
    def process_batch(self) -> int:
        def query(_start, _end):
            return lambda t: _start < t.rowid and t.rowid <= _end and \
                             t.metadata_type == REGULAR_TORRENT and \
                             t.tag_processor_version < self.version

        start = self.get_last_processed_torrent_id()
        max_row_id = self.mds.get_max_rowid()
        end = min(start + self.batch_size, max_row_id)
        self.logger.info(f'Processing batch [{start}...{end}]')

        batch = self.mds.TorrentMetadata.select(query(start, end))
        processed = 0
        added = 0
        for torrent in batch:
            added += self.process_torrent_title(torrent.infohash, torrent.title)
            torrent.tag_processor_version = self.version
            processed += 1

        self.mds.set_value(LAST_PROCESSED_TORRENT_ID, str(end))
        self.logger.info(f'Processed: {processed} titles. Added {added} tags.')

        is_finished = end >= max_row_id
        if is_finished:
            self.logger.info('Finish batch processing, cancel process_batch task')
            self.cancel_pending_task(name=self.process_batch.__name__)
        return processed

    def process_torrent_title(self, infohash: Optional[bytes] = None, title: Optional[str] = None) -> int:
        if not infohash or not title:
            return 0
        infohash_str = hexlify(infohash)
        if tags := set(extract_only_valid_tags(title, rules=general_rules)):
            self.save_statements(subject_type=ResourceType.TORRENT, subjects={infohash_str}, predicate=ResourceType.TAG,
                                 objects=tags)

        if content_items := set(extract_only_valid_tags(title, rules=content_items_rules)):
            self.save_statements(subject_type=ResourceType.TITLE, subjects=content_items, predicate=ResourceType.TORRENT,
                                 objects={infohash_str})

        return len(tags) + len(content_items)

    @db_session
    def save_statements(self, subject_type: ResourceType, subjects: Set[str], predicate: ResourceType, objects: Set[str]):
        self.logger.debug(f'Save: {len(objects)} objects and {len(subjects)} subjects with predicate={predicate}')
        for subject in subjects:
            for obj in objects:
                self.db.add_auto_generated(subject_type=subject_type, subject=subject, predicate=predicate, obj=obj)

    def get_last_processed_torrent_id(self) -> int:
        return int(self.mds.get_value(LAST_PROCESSED_TORRENT_ID, default='0'))
