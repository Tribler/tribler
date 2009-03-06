"""
Crawling the VideoPlayback statistics database
"""

import sys
import cPickle
import threading
from time import strftime

from Tribler.Core.BitTornado.BT1.MessageID import CRAWLER_VIDEOPLAYBACK_INFO_QUERY, CRAWLER_VIDEOPLAYBACK_EVENT_QUERY
from Tribler.Core.CacheDB.SqliteVideoPlaybackStatsCacheDB import VideoPlaybackEventDBHandler, VideoPlaybackInfoDBHandler
from Tribler.Core.Utilities.utilities import show_permid, show_permid_short
from Tribler.Core.Statistics.Crawler import Crawler
from Tribler.Core.Overlay.SecureOverlay import OLPROTO_VER_EIGHTH

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
            self._info_db = None
            self._event_db = None

        else:
            self._file = None
            self._info_db = VideoPlaybackInfoDBHandler.get_instance()
            self._event_db = VideoPlaybackEventDBHandler.get_instance()

    def query_info_initiator(self, permid, selversion, request_callback):
        """
        <<Crawler-side>>
        Established a new connection. Send a CRAWLER_VIDEOPLAYBACK_INFO_QUERY request.
        @param permid The Tribler peer permid
        @param selversion The oberlay protocol version
        @param request_callback Call this function one or more times to send the requests: request_callback(message_id, payload)
        """
        if selversion >= OLPROTO_VER_EIGHTH:
            if DEBUG: print >>sys.stderr, "videoplaybackcrawler: query_info_initiator", show_permid_short(permid)
            request_callback(CRAWLER_VIDEOPLAYBACK_INFO_QUERY, "SELECT timestamp, key, piece_size, nat FROM playback_info", callback=self._after_info_request_callback)
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

            for timestamp, key, piece_size, nat in info:
                # todo: optimize to not select key for each row
                request_callback(CRAWLER_VIDEOPLAYBACK_EVENT_QUERY, "SELECT timestamp, origin, event FROM playback_event WHERE key = '%s' ORDER BY timestamp ASC LIMIT 50; DELETE FROM playback_event WHERE key = '%s'; DELETE FROM playback_info WHERE key = '%s';" % (key, key, key), callback=self._after_info_request_callback)

    def _after_info_request_callback(self, exc, permid):
        """
        <<Crawler-side>>
        Called by the Crawler with the result of the request_callback
        call in the handle_crawler_reply method.
        """
        if not exc:
            if DEBUG: print >>sys.stderr, "videoplaybackcrawler: request send to", show_permid_short(permid)
            self._file.write("; ".join((strftime("%Y/%m/%d %H:%M:%S"), " INFO REQUEST", show_permid(permid), "\n")))
            self._file.flush()

    def handle_event_crawler_reply(self, permid, selversion, channel_id, error, message, request_callback):
        """
        <<Crawler-side>>
        Received a CRAWLER_VIDEOPLAYBACK_EVENT_QUERY reply.
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

            self._file.write("; ".join((strftime("%Y/%m/%d %H:%M:%S"), "  EVENT REPLY", show_permid(permid), str(error), message, "\n")))
            self._file.flush()

        else:
            if DEBUG:
                print >> sys.stderr, "videoplaybackcrawler: handle_crawler_reply", show_permid_short(permid), cPickle.loads(message)

            info = cPickle.loads(message)
            self._file.write("; ".join((strftime("%Y/%m/%d %H:%M:%S"), "  EVENT REPLY", show_permid(permid), str(error), str(info), "\n")))
            self._file.flush()

    def handle_crawler_request(self, permid, selversion, channel_id, message, reply_callback):
        """
        <<Peer-side>>
        Received a CRAWLER_VIDEOPLAYBACK_INFO_QUERY or a CRAWLER_VIDEOPLAYBACK_EVENT_QUERY request.
        @param permid The Crawler permid
        @param selversion The overlay protocol version
        @param channel_id Identifies a CRAWLER_REQUEST/CRAWLER_REPLY pair
        @param message The message payload
        @param reply_callback Call this function once to send the reply: reply_callback(payload [, error=123])
        """
        if DEBUG:
            print >> sys.stderr, "videoplaybackcrawler: handle_crawler_request", show_permid_short(permid), message

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

    
