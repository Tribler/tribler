import logging
from typing import Optional, Set

from ipv8.taskmanager import TaskManager

from pony.orm import db_session

import tribler_core.components.metadata_store.db.orm_bindings.torrent_metadata as torrent_metadata
import tribler_core.components.metadata_store.db.store as MDS
from tribler_core.components.metadata_store.db.serialization import REGULAR_TORRENT
from tribler_core.components.tag.db.tag_db import TagDatabase
from tribler_core.components.tag.rules.tag_rules import extract_only_valid_tags
from tribler_core.notifier import Notifier

DEFAULT_INTERVAL = 10
DEFAULT_BATCH_SIZE = 1000

LAST_PROCESSED_TORRENT_ID = 'last_processed_torrent_id'


class TagRulesProcessor(TaskManager):
    # this value must be incremented in the case of new rules set has been applied
    version: int = 1

    def __init__(self, notifier: Notifier, db: TagDatabase, mds: MDS.MetadataStore,
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
        self.notifier.add_observer(torrent_metadata.NEW_TORRENT_METADATA_CREATED,
                                   callback=self.process_torrent_title)
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
        tags = set(extract_only_valid_tags(title))
        if tags:
            self.save_tags(infohash, tags)
        return len(tags)

    @db_session
    def save_tags(self, infohash: bytes, tags: Set[str]):
        self.logger.debug(f'Save: {len(tags)} tags')
        for tag in tags:
            self.db.add_auto_generated_tag(infohash=infohash, tag=tag)

    def get_last_processed_torrent_id(self) -> int:
        return int(self.mds.get_value(LAST_PROCESSED_TORRENT_ID, default='0'))
