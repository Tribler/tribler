import logging
import time
from collections import deque

from Tribler.community.popularity.payload import SearchResponseItemPayload, ChannelItemPayload

MAX_CACHE = 200

DEFAULT_TORRENT_LIMIT = 25
DEFAULT_FRESHNESS_LIMIT = 60

TYPE_TORRENT_HEALTH = 1
TYPE_CHANNEL_HEALTH = 2


class ContentRepository(object):
    """
    This class handles all the stuffs related to the content for PopularityCommunity. Currently, it handles all the
    interactions with torrent and channel database.

    It also maintains a content queue which stores the content for publishing in the next publishing cycle.
    """

    def __init__(self, torrent_db, channel_db):
        super(ContentRepository, self).__init__()
        self.logger = logging.getLogger(self.__class__.__name__)
        self.torrent_db = torrent_db
        self.channel_db = channel_db
        self.queue = deque(maxlen=MAX_CACHE)

    def cleanup(self):
        self.torrent_db = None
        self.queue = None

    def add_content(self, content_type, content):
        if self.queue is not None:
            self.queue.append((content_type, content))

    def count_content(self):
        return len(self.queue) if self.queue else 0

    def pop_content(self):
        return self.queue.pop() if self.queue else (None, None)

    def get_top_torrents(self, limit=DEFAULT_TORRENT_LIMIT):
        return self.torrent_db.getRecentlyCheckedTorrents(limit)

    def update_torrent_health(self, torrent_health_payload, peer_trust=0):

        def update_torrent(db_handler, health_payload):
            db_handler.updateTorrent(infohash, notify=False, num_seeders=health_payload.num_seeders,
                                     num_leechers=health_payload.num_leechers,
                                     last_tracker_check=int(health_payload.timestamp),
                                     status=u"good" if health_payload.num_seeders > 1 else u"unknown")

        if not self.torrent_db:
            self.logger.error("Torrent DB is not available. Skipping torrent health update.")
            return

        infohash = torrent_health_payload.infohash
        if self.has_torrent(infohash):
            db_torrent = self.get_torrent(infohash)
            is_fresh = time.time() - db_torrent['last_tracker_check'] < DEFAULT_FRESHNESS_LIMIT
            if is_fresh and peer_trust < 2:
                self.logger.info("Database record is already fresh and the sending peer trust "
                                 "score is too low so we just ignore the response.")
                return

        # Update the torrent health anyway. A torrent info request should be sent separately to request additional info.
        update_torrent(self.torrent_db, torrent_health_payload)

    def update_torrent_info(self, torrent_info_response):
        infohash = torrent_info_response.infohash
        if self.has_torrent(infohash):
            db_torrent = self.get_torrent(infohash)
            if db_torrent['name'] and db_torrent['name'] == torrent_info_response.name:
                self.logger.info("Conflicting names for torrent. Ignoring the response")
                return

        # Update local database
        self.torrent_db.updateTorrent(infohash, notify=False, name=torrent_info_response.name,
                                      length=torrent_info_response.length,
                                      creation_date=torrent_info_response.creation_date,
                                      num_files=torrent_info_response.num_files,
                                      comment=torrent_info_response.comment)

    def get_torrent(self, infohash):
        keys = ('name', 'length', 'creation_date', 'num_files', 'num_seeders', 'num_leechers', 'comment',
                'last_tracker_check')
        return self.torrent_db.getTorrent(infohash, keys=keys, include_mypref=False)

    def has_torrent(self, infohash):
        return self.get_torrent(infohash) is not None

    def search_torrent(self, query):
        """
        Searches for best torrents for the given query and packs them into a list of SearchResponseItemPayload.
        :param query: Search query
        :return: List<SearchResponseItemPayload>
        """

        db_results = self.torrent_db.searchNames(query, local=True,
                                                 keys=['infohash', 'T.name', 'T.length', 'T.num_files', 'T.category',
                                                       'T.creation_date', 'T.num_seeders', 'T.num_leechers'])
        if not db_results:
            return []

        results = []
        for dbresult in db_results:
            channel_details = dbresult[-10:]

            dbresult = list(dbresult[:8])
            dbresult[2] = long(dbresult[2])  # length
            dbresult[3] = int(dbresult[3])  # num_files
            dbresult[4] = [dbresult[4]]  # category
            dbresult[5] = long(dbresult[5])  # creation_date
            dbresult[6] = int(dbresult[6] or 0)  # num_seeders
            dbresult[7] = int(dbresult[7] or 0)  # num_leechers

            # cid
            if channel_details[1]:
                channel_details[1] = str(channel_details[1])
            dbresult.append(channel_details[1])

            results.append(SearchResponseItemPayload(*tuple(dbresult)))

        return results

    def search_channels(self, query):
        """
        Search best channels for the given query.
        :param query: Search query
        :return: List<ChannelItemPayload>
        """
        db_channels = self.channel_db.search_in_local_channels_db(query)
        if not db_channels:
            return []

        results = []
        if db_channels:
            for channel in db_channels:
                channel_payload = channel[:8]
                channel_payload[7] = channel[8] # modified
                results.append(ChannelItemPayload(*channel_payload))
        return results

    def update_from_torrent_search_results(self, search_results):
        """
        Updates the torrent database with the provided search results. It also checks for conflicting torrents, meaning
        if torrent already exists in the database, we simply ignore the search result.
        """
        for result in search_results:
            (infohash, name, length, num_files, category_list, creation_date, seeders, leechers, cid) = result
            torrent_item = SearchResponseItemPayload(infohash, name, length, num_files, category_list,
                                                     creation_date, seeders, leechers, cid)
            if self.has_torrent(infohash):
                db_torrent = self.get_torrent(infohash)
                if db_torrent['name'] and db_torrent['name'] == torrent_item.name:
                    self.logger.info("Conflicting names for torrent. Ignoring the response")
                    continue
            else:
                self.logger.debug("Adding new torrent from search results to database")
                self.torrent_db.addOrGetTorrentID(infohash)

            # Update local database
            self.torrent_db.updateTorrent(infohash, notify=False, name=torrent_item.name,
                                          length=torrent_item.length,
                                          creation_date=torrent_item.creation_date,
                                          num_files=torrent_item.num_files,
                                          comment='')

    def update_from_channel_search_results(self, all_items):
        """
        TODO: updates the channel database with the search results.
        Waiting for all channel 2.0
        """
        pass
