# Written by Boudewijn Schoon
# see LICENSE.txt for license information

# todo
# - try to connect first, than start the initiator. now we start the
#   initiator and we often fail to connect

from traceback import print_exc
import random
import sys
import time

from Tribler.Core.BitTornado.BT1.MessageID import CRAWLER_REQUEST, CRAWLER_REPLY, getMessageName
from Tribler.Core.CacheDB.SqliteCacheDBHandler import CrawlerDBHandler
from Tribler.Core.Overlay.OverlayThreadingBridge import OverlayThreadingBridge
from Tribler.Core.Overlay.SecureOverlay import OLPROTO_VER_SEVENTH
from Tribler.Core.Utilities.utilities import show_permid_short

DEBUG = False

# when a message payload exceedes 32KB it is divided into multiple
# messages
MAX_PAYLOAD_LENGTH = 32 * 1024

# after 1 hour the channels for any outstanding CRAWLER_REQUEST
# messages will be closed
CHANNEL_TIMEOUT = 60 * 60

# the FREQUENCY_FLEXIBILITY tels the client how strict it must adhere
# to the frequency. the value indicates how many seconds a request
# will be allowed before the actual frequency deadline
FREQUENCY_FLEXIBILITY = 5

# Do not attempt to re-initiate communication after more than x
# connection failures
MAX_ALLOWED_FAILURES = 26

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

        # _crawl_initiators is a list with (initiator-callback,
        # frequency, accept_frequency) tuples the initiators are called
        # when a new connection is received
        self._crawl_initiators = []

        # _initiator_dealines contains [deadline, frequency,
        # accept_frequency, initiator-callback, permid, selversion,
        # failure-counter] deadlines register information on when to
        # call the crawl initiators again for a specific permid
        self._initiator_deadlines = []
        
        # _dialback_deadlines contains message_id:(deadline, permid) pairs
        # client peers should connect back to -a- crawler indicated by
        # permid after deadline expired
        self._dialback_deadlines = {}

        # _channels contains permid:buffer-dict pairs. Where
        # buffer_dict contains channel-id:(timestamp, buffer,
        # channel_data) pairs. Where buffer is the payload from
        # multipart messages that are received so far. Channels are
        # used to match outstanding replies to given requests
        self._channels = {}

        # start checking for expired deadlines
        self._check_deadlines(True)

        # start checking for ancient channels
        self._check_channels()

    def register_crawl_initiator(self, initiator_callback, frequency=3600, accept_frequency=None):
        """
        Register a callback that is called each time a new connection
        is made and subsequently each FREQUENCY seconds.

        ACCEPT_FREQUENCY defaults to FREQUENCY and indicates the
        minimum seconds that must expire before a crawler request
        message is accepted.

        Giving FREQUENCY = 10 and ACCEPT_FREQUENCY = 0 will call
        INITIATOR_CALLBACK every 10 seconds and will let the receiving
        peers accept allways.

        Giving FREQUENCY = 10 and ACCEPT_FREQUENCY = 20 will call
        INITIATOR_CALLBACK every 10 seconds and will cause frequency
        errors 50% of the time.
        """
        if accept_frequency is None:
            accept_frequency = frequency
        self._crawl_initiators.append((initiator_callback, frequency, accept_frequency))

    def register_message_handler(self, id_, request_callback, reply_callback):
        self._message_handlers[id_] = (request_callback, reply_callback, 0)

    def am_crawler(self):
        """
        Returns True if this running Tribler is a Crawler
        """
        return self._session.get_permid() in self._crawler_db.getCrawlers()

    def _acquire_channel_id(self, permid, channel_data):
        """
        Claim a unique one-byte id to match a request to a reply.

        PERMID the peer to communicate with
        CHANNEL_DATA optional data associated with this channel
        """
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
            if attempt > 64:
                channel_id = 0
                break
            channel_id = random.randint(1, 255)

        if channel_id == 0:
            # find a free channel-id sequentialy
            channel_id = 255
            while channel_id in channels and channel_id != 0:
                channel_id -= 1

        if channel_id:
            # create a buffer to receive the reply
            channels[channel_id] = [time.time() + CHANNEL_TIMEOUT, "", channel_data]

        # print >>sys.stderr, "crawler: _acquire_channel_id:", show_permid_short(permid), len(channels), "channels used"

        # a valid channel-id or 0 when no channel-id is left
        return channel_id

    def _release_channel_id(self, permid, channel_id):
        if permid in self._channels:
            if channel_id in self._channels[permid]:
                del self._channels[permid][channel_id]
            if not self._channels[permid]:
                del self._channels[permid]

    def _post_connection_attempt(self, permid, success):
        """
        This method is called after a succesfull or failed connection
        attempt
        """
        if success:
            # reset all failure counters for this permid
            for tup in (tup for tup in self._initiator_deadlines if tup[4] == permid):
                tup[6] = 0

        else:
            def increase_failure_counter(tup):
                if tup[4] == permid:
                    if tup[6] > MAX_ALLOWED_FAILURES:
                        # remove from self._initiator_deadlines
                        return False
                    else:
                        # increase counter but leave in self._initiator_deadlines
                        tup[6] += 1
                        return True
                else:
                    return True

            self._initiator_deadlines = filter(increase_failure_counter, self._initiator_deadlines)

    def send_request(self, permid, message_id, payload, frequency=3600, callback=None, channel_data=None):
        """
        This method ensures that a connection to PERMID exists before
        sending the message

        Returns the channel-id.

        MESSAGE_ID is a one character crawler specific ID (defined in MessageID.py).
        PAYLOAD is message specific sting.
        FREQUENCY is an integer defining the time, in seconds, until a next message with MESSAGE_ID is accepted by the client-side crawler.
        CALLBACK is either None or callable. Called with parameters EXC and PERMID. EXC is None for success or an Exception for failure.
        CHANNEL_DATA can be anything related to this specific request. It is supplied with the handle-reply callback.
        """
        # reserve a new channel-id
        channel_id = self._acquire_channel_id(permid, channel_data)

        def _after_connect(exc, dns, permid, selversion):
            self._post_connection_attempt(permid, not exc)
            if exc:
                # could not connect.
                if DEBUG: print >>sys.stderr, "crawler: could not connect", dns, show_permid_short(permid), exc
                self._release_channel_id(permid, channel_id)
                if callback:
                    callback(exc, permid)
            else:
                self._send_request(permid, message_id, channel_id, payload, frequency=frequency, callback=callback)

#         if DEBUG: print >>sys.stderr, "crawler: connecting (send_request)...", show_permid_short(permid)
        if channel_id == 0:
            if DEBUG: print >>sys.stderr, "crawler: send_request: Can not acquire channel-id", show_permid_short(permid)
        else:
            self._overlay_bridge.connect(permid, _after_connect)
        return channel_id

    def _send_request(self, permid, message_id, channel_id, payload, frequency=3600, callback=None):
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
        def _after_send_request(exc, permid):
            if DEBUG:
                if exc:
                    print >> sys.stderr, "crawler: could not send request to", show_permid_short(permid), exc
            if exc:
                self._release_channel_id(permid, channel_id)

            # call the optional callback supplied with send_request
            if callback:
                callback(exc, permid)

        if DEBUG: print >> sys.stderr, "crawler: sending", getMessageName(CRAWLER_REQUEST+message_id), "with", len(payload), "bytes payload to", show_permid_short(permid)
        self._overlay_bridge.send(permid, "".join((CRAWLER_REQUEST,
                                                   message_id,
                                                   chr(channel_id & 0xFF),
                                                   chr((frequency >> 8) & 0xFF) + chr(frequency & 0xFF),
                                                   str(payload))), _after_send_request)
        return channel_id

    def handle_request(self, permid, selversion, message):
        """
        Received CRAWLER_REQUEST message from OverlayApps
        """
        if selversion >= OLPROTO_VER_SEVENTH and len(message) >= 5:
            if message[1] in self._message_handlers:

                message_id = message[1]
                channel_id = ord(message[2])
                frequency = ord(message[3]) << 8 | ord(message[4])
                now = time.time()
                request_callback, reply_callback, last_request_timestamp = self._message_handlers[message_id]

                # frequency: we will report a requency error when we have
                # received this request within FREQUENCY seconds
                if last_request_timestamp + frequency < now + FREQUENCY_FLEXIBILITY:

                    if not permid in self._channels:
                        self._channels[permid] = {}
                    self._channels[permid][channel_id] = [time.time() + CHANNEL_TIMEOUT, "", None]

                    # store the new timestamp
                    self._message_handlers[message_id] = (request_callback, reply_callback, now)

                    def send_reply_helper(payload="", error=0, callback=None):
                        return self.send_reply(permid, message_id, channel_id, payload, error=error, callback=callback)

                    # 20/10/08. Boudewijn: We will no longer disconnect
                    # based on the return value from the message handler
                    try:
                        request_callback(permid, selversion, channel_id, message[5:], send_reply_helper)
                    except:
                        print_exc()

                    # 11/11/08. Boudewijn: Because the client peers may
                    # not always be connectable, the client peers will
                    # actively seek to connect to -a- crawler after
                    # frequency expires. 
                    self._dialback_deadlines[message_id] = (now + frequency, permid)

                    return True

                else:
                    # frequency error
                    self.send_reply(permid, message_id, channel_id, "frequency error", error=254)
                    return True
            else:
                # invalid / unknown message. may be caused by a
                # crawler sending newly introduced messages
                self.send_reply(permid, message_id, channel_id, "unknown message", error=253)
                return True
        else:
            # protocol version conflict or invalid message
            return False

    def send_reply(self, permid, message_id, channel_id, payload, error=0, callback=None):
        """
        This method ensures that a connection to PERMID exists before sending the message
        """
        def _after_connect(exc, dns, permid, selversion):
            self._post_connection_attempt(permid, not exc)
            if exc:
                # could not connect.
                if DEBUG: print >>sys.stderr, "crawler: could not connect", dns, show_permid_short(permid), exc
                if callback:
                    callback(exc, permid)
            else:
                self._send_reply(permid, message_id, channel_id, payload, error=error, callback=callback)

#         if DEBUG: print >>sys.stderr, "crawler: connecting... (send_reply)", show_permid_short(permid)
        self._overlay_bridge.connect(permid, _after_connect)

    def _send_reply(self, permid, message_id, channel_id, payload, error=0, callback=None):
        """
        Send a CRAWLER_REPLY message to permid. This method assumes
        that connection exists to the permid.
        
        @param permid The destination peer
        @param message_id The message id
        @param channel_id The channel id. Used to match replies to requests
        @param payload The message content
        @param error The error code. (0: no-error, 253: unknown-message, 254: frequency-error, 255: reserved)
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
                    print >> sys.stderr, "crawler: _after_send_reply", show_permid_short(permid), exc
                if not exc:
                    self.send_reply(permid, message_id, channel_id, remaining_payload, error=error)
                # call the optional callback supplied with send_request
                if callback:
                    callback(exc, permid)

            # 03/06/09 boudewijn: parts_left may be no larger than 255
            # because we only use one byte to store the 'parts
            # left'. This does not mean that there can't be more than
            # 255 parts!
            parts_left = min(255, int(len(payload) / MAX_PAYLOAD_LENGTH))
            payload = payload[:MAX_PAYLOAD_LENGTH]

        else:
            def _after_send_reply(exc, permid):
                if DEBUG:
                    if exc:
                        print >> sys.stderr, "crawler: could not send request", show_permid_short(permid), exc
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

        if DEBUG: print >> sys.stderr, "crawler: sending", getMessageName(CRAWLER_REPLY+message_id), "with", len(payload), "bytes payload to", show_permid_short(permid)
        self._overlay_bridge.send(permid, "".join((CRAWLER_REPLY,
                                                   message_id,
                                                   chr(channel_id & 0xFF),
                                                   chr(parts_left & 0xFF),
                                                   chr(error & 0xFF),
                                                   str(payload))), _after_send_reply)
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
                    timestamp, payload, channel_data = self._channels[permid].pop(channel_id)
                    if DEBUG:
                        if error == 253:
                            # unknown message error (probably because
                            # the crawler is newer than the peer)
                            print >> sys.stderr, "crawler: received", getMessageName(CRAWLER_REPLY+message_id), "with", len(message), "bytes payload from", show_permid_short(permid), "indicating an unknown message error"
                        if error == 254:
                            # frequency error (we did this request recently)
                            print >> sys.stderr, "crawler: received", getMessageName(CRAWLER_REPLY+message_id), "with", len(message), "bytes payload from", show_permid_short(permid), "indicating a frequency error"
                        else:
                            print >> sys.stderr, "crawler: received", getMessageName(CRAWLER_REPLY+message_id), "with", len(payload), "bytes payload from", show_permid_short(permid)
                    if not self._channels[permid]:
                        del self._channels[permid]

                    def send_request_helper(message_id, payload, frequency=3600, callback=None, channel_data=None):
                        return self.send_request(permid, message_id, payload, frequency=frequency, callback=callback, channel_data=channel_data)

                    # 20/10/08. Boudewijn: We will no longer
                    # disconnect based on the return value from the
                    # message handler
                    try:
                        # todo: update all code to always accept the channel_data parameter
                        if channel_data:
                            self._message_handlers[message_id][1](permid, selversion, channel_id, channel_data, error, payload, send_request_helper)
                        else:
                            self._message_handlers[message_id][1](permid, selversion, channel_id, error, payload, send_request_helper)
                    except:
                        print_exc()
                    return True
            else:
                # reply from unknown permid or channel
                if DEBUG: print >> sys.stderr, "crawler: received", getMessageName(CRAWLER_REPLY+message_id), "with", len(payload), "bytes payload from", show_permid_short(permid), "from unknown peer or unused channel"
                
        if DEBUG: print >> sys.stderr, "crawler: received", getMessageName(CRAWLER_REPLY+message_id), "with", len(payload), "bytes payload from", show_permid_short(permid), "from unknown peer or unused channel"
        return False

    def handle_connection(self, exc, permid, selversion, locally_initiated):
        """
        Called when overlay received a connection. Note that this
        method is only registered with OverlayApps when the command
        line option 'crawl' is used.
        """
        if exc:
            # connection lost
            if DEBUG: print >>sys.stderr, "crawler: overlay connection lost", show_permid_short(permid), exc

        elif selversion >= OLPROTO_VER_SEVENTH:
            # verify that we do not already have deadlines for this permid
            already_known = False
            for tup in self._initiator_deadlines:
                if tup[4] == permid:
                    already_known = True
                    break

            if not already_known:
                if DEBUG: print >>sys.stderr, "crawler: new overlay connection", show_permid_short(permid)
                for initiator_callback, frequency, accept_frequency in self._crawl_initiators:
                    self._initiator_deadlines.append([0, frequency, accept_frequency, initiator_callback, permid, selversion, 0])

                self._initiator_deadlines.sort()

                # Start sending crawler requests
                self._check_deadlines(False)
        else:
            if DEBUG: print >>sys.stderr, "crawler: new overlay connection (can not use version %d)" % selversion, show_permid_short(permid)
            
    def _check_deadlines(self, resubmit):
        """
        Send requests to permid and re-register to be called again
        after frequency seconds
        """
        now = time.time()

        # crawler side deadlines...
        if self._initiator_deadlines:
            for tup in self._initiator_deadlines:
                deadline, frequency, accept_frequency, initiator_callback, permid, selversion, failure_counter = tup
                if now > deadline + FREQUENCY_FLEXIBILITY:
                    def send_request_helper(message_id, payload, frequency=accept_frequency, callback=None, channel_data=None):
                        return self.send_request(permid, message_id, payload, frequency=frequency, callback=callback, channel_data=channel_data)
                    # 20/10/08. Boudewijn: We will no longer disconnect
                    # based on the return value from the message handler
                    try:
                        initiator_callback(permid, selversion, send_request_helper)
                    except Exception:
                        print_exc()

                    # set new deadline
                    tup[0] = now + frequency
                else:
                    break

            # resort
            self._initiator_deadlines.sort()

        # client side deadlines...
        if self._dialback_deadlines:

            def _after_connect(exc, dns, permid, selversion):
                if DEBUG:
                    if exc:
                        print >>sys.stderr, "crawler: dialback to crawler failed", dns, show_permid_short(permid), exc
                    else:
                        print >>sys.stderr, "crawler: dialback to crawler established", dns, show_permid_short(permid)

            for message_id, (deadline, permid) in self._dialback_deadlines.items():
                if now > deadline + FREQUENCY_FLEXIBILITY:
                    self._overlay_bridge.connect(permid, _after_connect)
                    del self._dialback_deadlines[message_id]

        if resubmit:
            self._overlay_bridge.add_task(lambda:self._check_deadlines(True), 5)

    def _check_channels(self):
        """
        Periodically removes permids after no connection was
        established for a long time
        """
        now = time.time()
        to_remove_permids = []
        for permid in self._channels:
            to_remove_channel_ids = []
            for channel_id, (deadline, _, _) in self._channels[permid].iteritems():
                if now > deadline:
                    to_remove_channel_ids.append(channel_id)
            for channel_id in to_remove_channel_ids:
                del self._channels[permid][channel_id]
            if not self._channels[permid]:
                to_remove_permids.append(permid)
        for permid in to_remove_permids:
            del self._channels[permid]

        # resubmit
        self._overlay_bridge.add_task(self._check_channels, 60)

