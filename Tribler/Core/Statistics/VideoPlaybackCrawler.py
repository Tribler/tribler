"""
Crawling the VideoPlayback statistics database
"""

from time import strftime
import cPickle
import sys
import threading
import zlib

from Tribler.Core.BitTornado.BT1.MessageID import CRAWLER_VIDEOPLAYBACK_INFO_QUERY, CRAWLER_VIDEOPLAYBACK_EVENT_QUERY
from Tribler.Core.CacheDB.SqliteVideoPlaybackStatsCacheDB import VideoPlaybackDBHandler
from Tribler.Core.Overlay.SecureOverlay import OLPROTO_VER_EIGHTH
from Tribler.Core.Statistics.Crawler import Crawler
from Tribler.Core.Utilities.utilities import show_permid, show_permid_short

DEBUG = False

class VideoPlaybackCrawler:
    __single = None    # used for multi-threaded singletons pattern
    lock = threading.Lock()

    @classmethod
    def get_instance(cls, *args, **kargs):
        # Singleton pattern with double-checking to ensure that it can only create one object
        if cls.__single is None:
            cls.lock.acquire()   
            try:
                if cls.__single is None:
                    cls.__single = cls(*args, **kargs)
            finally:
                cls.lock.release()
        return cls.__single
    
    def __init__(self):
        if VideoPlaybackCrawler.__single is not None:
            raise RuntimeError, "VideoPlaybackCrawler is singleton"

        crawler = Crawler.get_instance()
        if crawler.am_crawler():
            self._file = open("videoplaybackcrawler.txt", "a")
            self._file.write("".join(("# ", "*" * 80, "\n# ", strftime("%Y/%m/%d %H:%M:%S"), " Crawler started\n")))
            self._file.flush()
            self._event_db = None

        else:
            self._file = None
            self._event_db = VideoPlaybackDBHandler.get_instance()

    def query_initiator(self, permid, selversion, request_callback):
        """
        <<Crawler-side>>
        Established a new connection. Send a CRAWLER_VIDEOPLAYBACK_INFO_QUERY request.
        @param permid The Tribler peer permid
        @param selversion The oberlay protocol version
        @param request_callback Call this function one or more times to send the requests: request_callback(message_id, payload)
        """
        if selversion >= OLPROTO_VER_TEN:
            if DEBUG: print >>sys.stderr, "videoplaybackcrawler: query_initiator", show_permid_short(permid), "version", selversion
            # Overlay version 10 provided a simplification in the VOD
            # stats collecting. We now have only one database table:
            # playback_event that has only 3 columns: key, timestamp,
            # and event.
            request_callback(CRAWLER_VIDEOPLAYBACK_EVENT_QUERY, "SELECT key, timestamp, event FROM playback_event; DELETE FROM playback_event;", callback=self._after_event_request_callback)
            
        elif selversion >= OLPROTO_VER_EIGHTH:
            if DEBUG: print >>sys.stderr, "videoplaybackcrawler: query_initiator", show_permid_short(permid), "version", selversion
            # boudewijn: order the result DESC! From the resulting
            # list we will not remove the first entries from the
            # database because this (being the last item added) may
            # still be actively used.
            request_callback(CRAWLER_VIDEOPLAYBACK_INFO_QUERY, "SELECT key, timestamp, piece_size, num_pieces, bitrate, nat FROM playback_info ORDER BY timestamp DESC LIMIT 50", callback=self._after_info_request_callback)

        else:
            if DEBUG: print >>sys.stderr, "videoplaybackcrawler: query_info_initiator", show_permid_short(permid), "unsupported overlay version"

    def _after_info_request_callback(self, exc, permid):
        """
        <<Crawler-side>>
        Called by the Crawler with the result of the request_callback
        call in the query_initiator method.
        """
        if not exc:
            if DEBUG: print >>sys.stderr, "videoplaybackcrawler: request send to", show_permid_short(permid)
            self._file.write("; ".join((strftime("%Y/%m/%d %H:%M:%S"), "INFO REQUEST", show_permid(permid), "\n")))
            self._file.flush()

    def handle_info_crawler_reply(self, permid, selversion, channel_id, error, message, request_callback):
        """
        <<Crawler-side>>
        Received a CRAWLER_VIDEOPLAYBACK_INFO_QUERY reply.
        @param permid The Crawler permid
        @param selversion The overlay protocol version
        @param channel_id Identifies a CRAWLER_REQUEST/CRAWLER_REPLY pair
        @param error The error value. 0 indicates success.
        @param message The message payload
        @param request_callback Call this function one or more times to send the requests: request_callback(message_id, payload)
        """
        if error:
            if DEBUG:
                print >> sys.stderr, "videoplaybackcrawler: handle_crawler_reply", error, message

            self._file.write("; ".join((strftime("%Y/%m/%d %H:%M:%S"), "   INFO REPLY", show_permid(permid), str(error), message, "\n")))
            self._file.flush()

        else:
            if DEBUG:
                print >> sys.stderr, "videoplaybackcrawler: handle_crawler_reply", show_permid_short(permid), cPickle.loads(message)

            info = cPickle.loads(message)
            self._file.write("; ".join((strftime("%Y/%m/%d %H:%M:%S"), "   INFO REPLY", show_permid(permid), str(error), str(info), "\n")))
            self._file.flush()

            i = 0
            for key, timestamp, piece_size, num_pieces, bitrate, nat in info:
                i += 1
                # do not remove the first item. the list is ordered
                # DESC so the first item is the last that is added to
                # the database and we can't affored to remove it, as
                # it may cause exceptions in the running playback.
                if i == 1:
                    sql = "SELECT timestamp, origin, event FROM playback_event WHERE key = '%s' ORDER BY timestamp ASC LIMIT 50" % key
                else:
                    sql = "SELECT timestamp, origin, event FROM playback_event WHERE key = '%s' ORDER BY timestamp ASC LIMIT 50; DELETE FROM playback_event WHERE key = '%s'; DELETE FROM playback_info WHERE key = '%s';" % (key, key, key)
                    
                # todo: optimize to not select key for each row
                request_callback(CRAWLER_VIDEOPLAYBACK_EVENT_QUERY, sql, channel_data=key, callback=self._after_event_request_callback, frequency=0)

    def _after_event_request_callback(self, exc, permid):
        """
        <<Crawler-side>>
        Called by the Crawler with the result of the request_callback
        call in the handle_crawler_reply method.
        """
        if not exc:
            if DEBUG: print >>sys.stderr, "videoplaybackcrawler: request send to", show_permid_short(permid)
            self._file.write("; ".join((strftime("%Y/%m/%d %H:%M:%S"), " INFO REQUEST", show_permid(permid), "\n")))
            self._file.flush()

    def handle_event_crawler_reply(self, permid, selversion, channel_id, channel_data, error, message, request_callback):
        """
        <<Crawler-side>>
        Received a CRAWLER_VIDEOPLAYBACK_EVENT_QUERY reply.
        @param permid The Crawler permid
        @param selversion The overlay protocol version
        @param channel_id Identifies a CRAWLER_REQUEST/CRAWLER_REPLY pair
        @param channel_data Data associated with the request
        @param error The error value. 0 indicates success.
        @param message The message payload
        @param request_callback Call this function one or more times to send the requests: request_callback(message_id, payload)
        """
        if error:
            if DEBUG:
                print >> sys.stderr, "videoplaybackcrawler: handle_crawler_reply", error, message

            self._file.write("; ".join((strftime("%Y/%m/%d %H:%M:%S"), "  EVENT REPLY", show_permid(permid), str(error), channel_data, message, "\n")))
            self._file.flush()

        elif selversion >= OLPROTO_VER_TEN:
            # Overlay version 10 sends the reply pickled and zipped
            if DEBUG:
                print >> sys.stderr, "videoplaybackcrawler: handle_crawler_reply", show_permid_short(permid), len(message), "bytes zipped"

            info = cPickle.loads(zlib.decompress(message))
            self._file.write("; ".join((strftime("%Y/%m/%d %H:%M:%S"), "  EVENT REPLY", show_permid(permid), str(error), channel_data, str(info), "\n")))
            self._file.flush()
            
        elif selversion >= OLPROTO_VER_EIGHTH:
            if DEBUG:
                print >> sys.stderr, "videoplaybackcrawler: handle_crawler_reply", show_permid_short(permid), cPickle.loads(message)

            info = cPickle.loads(message)
            self._file.write("; ".join((strftime("%Y/%m/%d %H:%M:%S"), "  EVENT REPLY", show_permid(permid), str(error), channel_data, str(info), "\n")))
            self._file.flush()

    def handle_event_crawler_request(self, permid, selversion, channel_id, message, reply_callback):
        """
        <<Peer-side>>
        Received a CRAWLER_VIDEOPLAYBACK_EVENT_QUERY request.
        @param permid The Crawler permid
        @param selversion The overlay protocol version
        @param channel_id Identifies a CRAWLER_REQUEST/CRAWLER_REPLY pair
        @param message The message payload
        @param reply_callback Call this function once to send the reply: reply_callback(payload [, error=123])
        """
        if DEBUG:
            print >> sys.stderr, "videoplaybackcrawler: handle_event_crawler_request", show_permid_short(permid), message

        # execute the sql
        try:
            cursor = self._event_db._db.execute_read(message)

        except Exception, e:
            reply_callback(str(e), error=1)
        else:
            if cursor:
                reply_callback(zlib.compress(cPickle.dumps(list(cursor), 2), 9))
            else:
                reply_callback("error", error=2)

    
