from __future__ import absolute_import

import logging
import time
from collections import deque

from pony.orm import db_session, desc

from Tribler.Core.Modules.MetadataStore.serialization import REGULAR_TORRENT
from Tribler.pyipv8.ipv8.database import database_blob

try:
    long        # pylint: disable=long-builtin
except NameError:
    long = int  # pylint: disable=redefined-builtin

MAX_CACHE = 200

DEFAULT_TORRENT_LIMIT = 25
DEFAULT_FRESHNESS_LIMIT = 60

TYPE_TORRENT_HEALTH = 1


class ContentRepository(object):
    """
    This class handles all the stuffs related to the content for PopularityCommunity. Currently, it handles all the
    interactions with torrent and channel database.

    It also maintains a content queue which stores the content for publishing in the next publishing cycle.
    """

    def __init__(self, metadata_store):
        super(ContentRepository, self).__init__()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.metadata_store = metadata_store
        self.queue = deque(maxlen=MAX_CACHE)

    def cleanup(self):
        self.queue = None

    def add_content_to_queue(self, content):
        if self.queue is not None:
            self.queue.append(content)

    def queue_length(self):
        return len(self.queue) if self.queue else 0

    def pop_content(self):
        return self.queue.pop() if self.queue else None

    @db_session
    def get_top_torrents(self, limit=DEFAULT_TORRENT_LIMIT):
        return list(self.metadata_store.TorrentMetadata.select(
            lambda g: g.metadata_type == REGULAR_TORRENT).sort_by(desc("g.health.seeders")).limit(limit))

    @db_session
    def update_torrent_health(self, torrent_health_payload, peer_trust=0):
        """
        Update the health of a torrent in the database.
        """
        if not self.metadata_store:
            self.logger.error("Metadata store is not available. Skipping torrent health update.")
            return

        infohash = torrent_health_payload.infohash
        if not self.has_torrent(infohash):
            return

        torrent = self.get_torrent(infohash)
        is_fresh = time.time() - torrent.health.last_check < DEFAULT_FRESHNESS_LIMIT
        if is_fresh and peer_trust < 2:
            self.logger.info("Database record is already fresh and the sending peer trust "
                             "score is too low so we just ignore the response.")
        else:
            # Update the torrent health anyway. A torrent info request should be sent separately
            # to request additional info.
            torrent.health.seeders = torrent_health_payload.num_seeders
            torrent.health.leechers = torrent_health_payload.num_leechers
            torrent.health.last_check = int(torrent_health_payload.timestamp)

    @db_session
    def get_torrent(self, infohash):
        """
        Return a torrent with a specific infohash from the database.
        """
        results = list(self.metadata_store.TorrentMetadata.select(
            lambda g: g.infohash == database_blob(infohash) and g.metadata_type == REGULAR_TORRENT).limit(1))
        if results:
            return results[0]
        return None

    def has_torrent(self, infohash):
        return self.get_torrent(infohash) is not None
