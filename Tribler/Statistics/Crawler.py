# Written by Boudewijn Schoon
# see LICENSE.txt for license information

# TODO: 
# - modify lucia's stuff to new directory structure

import cPickle
import random
import sys
import time

from Tribler.Core.BitTornado.BT1.MessageID import CRAWLER_REQUEST, CRAWLER_REPLY
from Tribler.Core.CacheDB.SqliteCacheDBHandler import CrawlerDBHandler
from Tribler.Core.Overlay.OverlayThreadingBridge import OverlayThreadingBridge
from Tribler.Core.Overlay.SecureOverlay import OLPROTO_VER_SEVENTH

DEBUG = False

# when a message payload exceedes 32KB it is divided into multiple
# messages
MAX_PAYLOAD_LENGTH = 32 * 1024

# after 6 hours the channels for any outstanding CRAWLER_REQUEST
# messages will be closed
CHANNEL_TIMEOUT = 6 * 60 * 60 

class Crawler:
    __singleton = None

    @classmethod
    def get_instance(cls, *args, **kargs):
        if not cls.__singleton:
            cls.__singleton = cls(*args, **kargs)
        return cls.__singleton

    def __init__(self, session):
        if self.__singleton:
            raise RuntimeError, "Crawler is Singleton"
        Crawler.__single = self 
        self._overlay_bridge = OverlayThreadingBridge.getInstance()
        self._session = session
        self._crawler_db = CrawlerDBHandler.getInstance()

        # _message_handlers contains message-id:(request-callback, reply-callback, last-request-timestamp)
        # the handlers are called when either a CRAWL_REQUEST or CRAWL_REPLY message is received
        self._message_handlers = {}

        # _crawl_initiators is a list with (initiator-callback, frequency)
        # the initiators are called when a new connection is received
        self._crawl_initiators = []

        # _dealines contains (deadline, frequency, initiator-callback, permid, selversion)
        # deadlines register information on when to call the crawl initiators again for a specific permid
        self._deadlines = []
        
        # _channels contains permid:buffer-dict pairs. Where
        # buffer_dict contains channel-id:(timestamp, buffer)
        # pairs. Where buffer is the payload from multipart messages
        # that are received so far.
        # channels are used to match outstanding replies to given requests
        self._channels = {}

        # start checking for expired deadlines
        self._check_deadlines(True)

        # start checking for ancient channels
        self._check_channels()

    def register_crawl_initiator(self, initiator_callback, frequency=3600):
        self._crawl_initiators.append((initiator_callback, frequency))

    def register_message_handler(self, id_, request_callback, reply_callback):
        self._message_handlers[id_] = (request_callback, reply_callback, 0)

    def am_crawler(self):
        """
        Returns True if this running Tribler is a Crawler
        """
        return self._session.get_permid() in self._crawler_db.getCrawlers()

    def send_request(self, permid, message_id, payload, frequency=3600, callback=None):
        """
        This method ensures that a connection to PERMID exists before sending the message
        """
        def _after_connect(exc, dns, permid, selversion):
            if exc:
                # could not connect.
                if callback:
                    callback(exc, permid)
            else:
                _send_request(permid, message_id, payload, frequency=frequency, callback=callback)

        self._overlay_bridge.connect(permid, _after_connect)

    def _send_request(self, permid, message_id, payload, frequency=3600, callback=None):
        """
        Send a CRAWLER_REQUEST message to permid. This method assumes
        that connection exists to the permid.

        @param permid The destination peer
        @param message_id The message id
        @param payload The message content
        @param frequency Destination peer will return a frequency-error when this message_id has been received within the last frequency seconds
        @param callback Callable function/method is called when request is send with 2 paramaters (exc, permid)
        @return The message channel-id > 0 on success, and 0 on failure
        """
        # Sending a request from a Crawler to a Tribler peer
        #     SIZE    INDEX
        #     1 byte: 0      CRAWLER_REQUEST (from Tribler.Core.BitTornado.BT1.MessageID)
        #     1 byte: 1      --MESSAGE-SPECIFIC-ID--
        #     1 byte: 2      Channel id
        #     2 byte: 3+4    Frequency
        #     n byte: 5...   Request payload

        # reserve a new channel-id
        if permid in self._channels:
            channels = self._channels[permid]
        else:
            channels = {}
            self._channels[permid] = channels

        # find a free channel-id randomly
        channel_id = random.randint(1, 255)
        attempt = 0
        while channel_id in channels:
            attempt += 1
            if attempt > 128:
                channel_id = 0
                break
            channel_id = random.randint(1, 255)

        if channel_id == 0:
            # find a free channel-id sequentialy
            channel_id = 255
            while channel_id in channels and channel_id != 0:
                channel_id -= 1

            if channel_id == 0:
                # no channel-id's left
                return 0

        # create a buffer to receive the reply
        channels[channel_id] = (time.time() + CHANNEL_TIMEOUT, "")

        def _after_send_request(exc, permid):
            if DEBUG:
                if exc:
                    print >> sys.stderr, "crawler: could not send request", exc
            if exc:
                if permid in self._channels and channel_id in self._channels[permid]:
                    del self._channels[permid][channel_id]

            # call the optional callback supplied with send_request
            if callback:
                callback(exc, permid)
        
        if DEBUG:
            print >> sys.stderr, "crawler: sending request message with", len(payload), "bytes payload"
        self._overlay_bridge.send(permid, "".join((CRAWLER_REQUEST,
                                                   message_id,
                                                   chr(channel_id & 0xFF),
                                                   chr((frequency >> 8) & 0xFF) + chr(frequency & 0xFF),
                                                   payload)), _after_send_request)
        return channel_id

    def handle_request(self, permid, selversion, message):
        """
        Received CRAWLER_REQUEST message from OverlayApps
        """
        if selversion >= OLPROTO_VER_SEVENTH and len(message) >= 5 and message[1] in self._message_handlers:

            now = time.time()
            message_id = message[1]
            channel_id = ord(message[2])
            frequency = ord(message[3]) << 8 | ord(message[4])

            if permid in self._channels:
                channels = self._channels[permid]
            else:
                channels = {}
                self._channels[permid] = channels

            if channel_id in channels:
                # channel-id must be unused (this can occur when two
                # crawlers send requests to eachother)
                return False
            else:
                channels[channel_id] = (time.time() + CHANNEL_TIMEOUT, "")

            request_callback, reply_callback, last_request_timestamp = self._message_handlers[message_id]

            # frequency: we will report a requency error when we have
            # received this request within FREQUENCY seconds
            if last_request_timestamp + frequency < now:

                # store the new timestamp
                self._message_handlers[message_id] = (request_callback, reply_callback, now)

                return request_callback(permid, selversion, channel_id, message[5:], lambda payload="", error=0:self.send_reply(permid, message_id, channel_id, payload, error))

            else:
                # frequency error
                send_reply(permid, message_id, channel_id, "frequency error", error=254)
                return True
        else:
            # protocol version conflict or invalid message
            return False

    def send_reply(self, permid, message_id, channel_id, payload, error=0, callback=None):
        """
        This method ensures that a connection to PERMID exists before sending the message
        """
        def _after_connect(exc, dns, permid, selversion):
            if exc:
                # could not connect.
                if callback:
                    callback(exc, permid)
            else:
                _send_reply(permid, message_id, channel_id, payload, error=error, callback=callback)

        self._overlay_bridge.connect(permid, _after_connect)

    def _send_reply(self, permid, message_id, channel_id, payload, error=0, callback=None):
        """
        Send a CRAWLER_REPLY message to permid. This method assumes
        that connection exists to the permid.
        
        @param permid The destination peer
        @param message_id The message id
        @param channel_id The channel id. Used to match replies to requests
        @param payload The message content
        @param error The error code. (0: no-error, 254: frequency-error, 255: reserved)
        @param callback Callable function/method is called when request is send with 2 paramaters (exc, permid)
        @return The message channel-id > 0 on success, and 0 on failure
        """
        # Sending a reply from a Tribler peer to a Crawler
        #     SIZE    INDEX
        #     1 byte: 0      CRAWLER_REPLY (from Tribler.Core.BitTornado.BT1.MessageID)
        #     1 byte: 1      --MESSAGE-SPECIFIC-ID--
        #     1 byte: 2      Channel id
        #     1 byte: 3      Parts left
        #     1 byte: 4      Indicating success (0) or failure (non 0)
        #     n byte: 5...   Reply payload

        if len(payload) > MAX_PAYLOAD_LENGTH:
            remaining_payload = payload[MAX_PAYLOAD_LENGTH:]

            def _after_send_reply(exc, permid):
                """
                Called after the overlay attempted to send a reply message
                """
                if DEBUG:
                    print >> sys.stderr, "crawler: _after_send_reply"
                if not exc:
                    self.send_reply(permid, message_id, channel_id, remaining_payload, error=error)
                # call the optional callback supplied with send_request
                if callback:
                    callback(exc, permid)

            parts_left = int(len(payload) / MAX_PAYLOAD_LENGTH)
            payload = payload[:MAX_PAYLOAD_LENGTH]

        else:
            def _after_send_reply(exc, permid):
                if DEBUG:
                    if exc:
                        print >> sys.stderr, "crawler: could not send request", exc
                # call the optional callback supplied with send_request
                if callback:
                    callback(exc, permid)

            parts_left = 0

            # remove from self._channels if it is still there (could
            # have been remove during periodic timeout check)
            if permid in self._channels and channel_id in self._channels[permid]:
                del self._channels[permid][channel_id]
                if not self._channels[permid]:
                    del self._channels[permid]

        if DEBUG:
            print >> sys.stderr, "crawler: sending reply message with", len(payload), "bytes payload (", parts_left, "parts left )"
        self._overlay_bridge.send(permid, "".join((CRAWLER_REPLY,
                                                   message_id,
                                                   chr(channel_id & 0xFF),
                                                   chr(parts_left & 0xFF),
                                                   chr(error & 0xFF),
                                                   payload)), _after_send_reply)
        return channel_id

    def handle_reply(self, permid, selversion, message):
        """
        Received CRAWLER_REPLY message from OverlayApps
        """
        if selversion >= OLPROTO_VER_SEVENTH and len(message) >= 5 and message[1] in self._message_handlers:
            
            message_id = message[1]
            channel_id = ord(message[2])
            parts_left = ord(message[3])
            error = ord(message[4])

            # A request must exist in self._channels, otherwise we did
            # not request this reply
            if permid in self._channels and channel_id in self._channels[permid]:

                # add part to buffer
                self._channels[permid][channel_id][1] += message[5:]

                if parts_left:
                    # todo: register some event to remove the buffer
                    # after a time (in case connection is lost before
                    # all parts are received)

                    # Can't do anything until all parts have been received
                    return True
                else:
                    timestamp, payload = self._channels[permid].pop(channel_id)
                    if not self._channels[permid]:
                        del self._channels[permid]
                    return self._message_handlers[message_id][1](permid, selversion, channel_id, payload, lambda message_id, payload:self.send_request(permid, message_id, payload, frequency=frequency))
        return False

    def handle_connection(self, exc, permid, selversion, locally_initiated):
        """
        Called when overlay received a connection. Note that this
        method is only registered with OverlayApps when the command
        line option 'crawl' is used.
        """
        if exc:
            # connection lost
            if DEBUG: print >>sys.stderr, "crawler: overlay connection lost"

        else:
            if DEBUG: print >>sys.stderr, "crawler: new overlay connection"

            for initiator_callback, frequency in self._crawl_initiators:
                self._deadlines.append([0, frequency, initiator_callback, permid, selversion])

            self._deadlines.sort()

            # Start sending crawler requests
            self._check_deadlines(False)
            
    def _check_deadlines(self, resubmit):
        """
        Send requests to permid and re-register to be called again
        after frequency seconds
        """
        now = time.time()
        while self._deadlines:
            deadline, frequency, initiator_callback, permid, selversion = self._deadlines[0]
            if now > deadline:
                initiator_callback(permid, selversion, lambda message_id, payload:self.send_request(permid, message_id, payload, frequency=frequency))

                # set new deadline
                self._deadlines[0][0] = now + frequency
            else:
                break

        # resort
        self._deadlines.sort()
            
        if resubmit:
            self._overlay_bridge.add_task(lambda:self._check_deadlines(True), 5)

    def _check_channels(self):
        """
        Periodically removes permids after no connection was
        established for a long time
        """
        now = time.time()
        for permid in self._channels:
            for channel_id, (deadline, buffer_) in self._channels[permid].iteritems():
                if now > deadline:
                    del self._channels[permid][channel_id]
            if not self._channels[permid]:
                del self._channels[permid]

        # resubmit
        self._overlay_bridge.add_task(self._check_channels, 60)

