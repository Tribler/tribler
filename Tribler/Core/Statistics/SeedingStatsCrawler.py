# see LICENSE.txt for license information

from Tribler.Core.CacheDB.sqlitecachedb import SQLiteCacheDB

class SeedingStatsCrawler:
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
        if DEBUG: 
            print >>sys.stderr, "crawler: SeedingStatsDB_query_initiator"
        return request_callback(CRAWLER_SEEDINGSTATS_QUERY, "SELECT * FROM SeedingStats WHERE crawled = 0 and timestamp <=%s ORDER BY timestamp DESC"%time())

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
            print >> sys.stderr, "crawler: handle_crawler_SeedingStats_request", message

        # execute the sql
        try:
            cursor = self._sqlite_cache_db.execute_read(message)
        except Exception, e:
            reply_callback(str(e), 1)
        else:
            if cursor:
                res = list(cursor)
                reply_callback(cPickle.dumps(res, 2))

                # set crawled flag to 1
                sql_update = 'UPDATE SeedingStats SET crawled=1 WHERE crawled=0 and timestamp <=%s'%res[0][0]
                self._sqlite_cache_db.execute_write(sql_update)
            else:
                reply_callback("error", 1)

        return True

    def handle_crawler_reply(self, permid, selversion, channel_id, message, reply_callback):
        """
        Received a CRAWLER_DATABASE_QUERY request.
        @param permid The Crawler permid
        @param selversion The overlay protocol version
        @param channel_id Identifies a CRAWLER_REQUEST/CRAWLER_REPLY pair
        @param message The message payload
        @param request_callback Call this function one or more times to send the requests: request_callback(message_id, payload)
        """
        if DEBUG:
            print >> sys.stderr, "olapps: handle_crawler_SeedingStats_reply"

        try:
            results = cPickle.loads(message, 2)
            values = map(tuple, results)
            self._sqlite_cache_db.insertMany("SeedingStats", values)
        except Exception, e:
            print_exc()
            return False

        return True
