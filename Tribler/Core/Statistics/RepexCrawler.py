# Based on DatabaseCrawler.py written by Boudewijn Schoon
# Modified by Raynor Vliegendhart
# see LICENSE.txt for license information

import sys
import cPickle
import base64
from time import strftime

from Tribler.Core.BitTornado.BT1.MessageID import CRAWLER_REPEX_QUERY
from Tribler.Core.Utilities.utilities import show_permid, show_permid_short
from Tribler.Core.Statistics.Crawler import Crawler

from Tribler.Core.DecentralizedTracking.repex import RePEXLogDB

DEBUG = False

"""
repexcrawler.txt:

# ******************************************************************************
# 2009/10/14 10:12:46 Crawler started
2009/10/14 10:14:03; REQUEST; permid;
2009/10/14 10:17:42;   REPLY; permid; 0; base64_pickle_peerhistory;
2009/10/14 10:19:54;   REPLY; permid; 1; exception_msg;
"""

class RepexCrawler:
    __single = None

    @classmethod
    def get_instance(cls, *args, **kargs):
        if not cls.__single:
            cls.__single = cls(*args, **kargs)
        return cls.__single

    def __init__(self,session):
        crawler = Crawler.get_instance()
        if crawler.am_crawler():
            self._file = open("repexcrawler.txt", "a")
            self._file.write("".join(("# ", "*" * 78, "\n# ", strftime("%Y/%m/%d %H:%M:%S"), " Crawler started\n")))
            self._file.flush()
            self._repexlog = None
        else:
            self._file = None
            self._repexlog = RePEXLogDB.getInstance(session)

    def query_initiator(self, permid, selversion, request_callback):
        """
        Established a new connection. Send a CRAWLER_REPEX_QUERY request.
        @param permid The Tribler peer permid
        @param selversion The overlay protocol version
        @param request_callback Call this function one or more times to send the requests: request_callback(message_id, payload)
        """
        if DEBUG: print >>sys.stderr, "repexcrawler: query_initiator", show_permid_short(permid)
        
        request_callback(CRAWLER_REPEX_QUERY, '', callback=self._after_request_callback)

    def _after_request_callback(self, exc, permid):
        """
        Called by the Crawler with the result of the request_callback
        call in the query_initiator method.
        """
        if not exc:
            if DEBUG: print >>sys.stderr, "repexcrawler: request sent to", show_permid_short(permid)
            self._file.write("; ".join((strftime("%Y/%m/%d %H:%M:%S"), "REQUEST", show_permid(permid), "\n")))
            self._file.flush()

    def handle_crawler_request(self, permid, selversion, channel_id, message, reply_callback):
        """
        Received a CRAWLER_REPEX_QUERY request.
        @param permid The Crawler permid
        @param selversion The overlay protocol version
        @param channel_id Identifies a CRAWLER_REQUEST/CRAWLER_REPLY pair
        @param message The message payload
        @param reply_callback Call this function once to send the reply: reply_callback(payload [, error=123])
        """
        if DEBUG:
            print >> sys.stderr, "repexcrawler: handle_crawler_request", show_permid_short(permid), message

        # retrieve repex history
        try:
            repexhistory = self._repexlog.getHistoryAndCleanup()

        except Exception, e:
            reply_callback(str(e), error=1)
        else:
            reply_callback(cPickle.dumps(repexhistory, 2))

    def handle_crawler_reply(self, permid, selversion, channel_id, channel_data, error, message, request_callback):
        """
        Received a CRAWLER_REPEX_QUERY reply.
        @param permid The Crawler permid
        @param selversion The overlay protocol version
        @param channel_id Identifies a CRAWLER_REQUEST/CRAWLER_REPLY pair
        @param error The error value. 0 indicates success.
        @param message The message payload
        @param request_callback Call this function one or more times to send the requests: request_callback(message_id, payload)
        """
        if error:
            if DEBUG:
                print >> sys.stderr, "repexcrawler: handle_crawler_reply", error, message

            self._file.write("; ".join((strftime("%Y/%m/%d %H:%M:%S"), "  REPLY", show_permid(permid), str(error), message, "\n")))
            self._file.flush()

        else:
            if DEBUG:
                print >> sys.stderr, "repexcrawler: handle_crawler_reply", show_permid_short(permid), cPickle.loads(message)
            
            # The message is pickled, which we will just write to file.
            # To make later parsing easier, we base64 encode it
            self._file.write("; ".join((strftime("%Y/%m/%d %H:%M:%S"), "  REPLY", show_permid(permid), str(error), base64.b64encode(message), "\n")))
            self._file.flush()

