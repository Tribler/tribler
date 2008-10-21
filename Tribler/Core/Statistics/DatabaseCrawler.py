# Written by Boudewijn Schoon
# see LICENSE.txt for license information

import sys
import cPickle

from Tribler.Core.BitTornado.BT1.MessageID import CRAWLER_DATABASE_QUERY
from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB
from Tribler.Core.Utilities.utilities import show_permid_short

DEBUG = True

class DatabaseCrawler:
    __single = None

    @classmethod
    def get_instance(cls, *args, **kargs):
        if not cls.__single:
            cls.__single = cls(*args, **kargs)
        return cls.__single

    def __init__(self):
        self._sqlite_cache_db = SQLiteCacheDB.getInstance()

    def query_initiator(self, permid, selversion, request_callback):
        """
        Established a new connection. Send a CRAWLER_DATABASE_QUERY request.
        @param permid The Tribler peer permid
        @param selversion The oberlay protocol version
        @param request_callback Call this function one or more times to send the requests: request_callback(message_id, payload)
        """
        if DEBUG: print >>sys.stderr, "databasecrawler: query_initiator", show_permid_short(permid)
        request_callback(CRAWLER_DATABASE_QUERY, "SELECT 'peer_count', count(*) FROM Peer; SELECT 'torrent_count', count(*) FROM Torrent")

    def handle_crawler_request(self, permid, selversion, channel_id, message, reply_callback):
        """
        Received a CRAWLER_DATABASE_QUERY request.
        @param permid The Crawler permid
        @param selversion The overlay protocol version
        @param channel_id Identifies a CRAWLER_REQUEST/CRAWLER_REPLY pair
        @param message The message payload
        @param reply_callback Call this function once to send the reply: reply_callback(payload [, error=123])
        """
        if DEBUG:
            print >> sys.stderr, "databasecrawler: handle_crawler_request", show_permid_short(permid), message

        # execute the sql
        try:
            cursor = self._sqlite_cache_db.execute_read(message)

        except Exception, e:
            reply_callback(str(e), error=1)
        else:
            if cursor:
                reply_callback(cPickle.dumps(list(cursor), 2))
            else:
                reply_callback("error", error=2)

        return True

    def handle_crawler_reply(self, permid, selversion, channel_id, error, message, request_callback):
        """
        Received a CRAWLER_DATABASE_QUERY request.
        @param permid The Crawler permid
        @param selversion The overlay protocol version
        @param channel_id Identifies a CRAWLER_REQUEST/CRAWLER_REPLY pair
        @param error The error value. 0 indicates success.
        @param message The message payload
        @param request_callback Call this function one or more times to send the requests: request_callback(message_id, payload)
        """
        if error:
            if DEBUG:
                print >> sys.stderr, "databasecrawler: handle_crawler_reply"
                print >> sys.stderr, "databasecrawler: error", error, message
        else:
            print >> sys.stderr, "databasecrawler: handle_crawler_reply", show_permid_short(permid), cPickle.loads(message)

        return True
