import logging
import random
import struct
import time
from abc import ABCMeta, abstractmethod, abstractproperty
from libtorrent import bdecode
from twisted.internet import reactor, defer
from twisted.internet.defer import Deferred, inlineCallbacks
from twisted.internet.protocol import DatagramProtocol
from twisted.python.failure import Failure
from twisted.web.client import Agent, readBody, RedirectAgent, HTTPConnectionPool

from Tribler.Core.Utilities.encoding import add_url_params
from Tribler.Core.Utilities.tracker_utils import parse_tracker_url
from Tribler.dispersy.util import call_on_reactor_thread
from Tribler.pyipv8.ipv8.taskmanager import TaskManager

# Although these are the actions for UDP trackers, they can still be used as
# identifiers.
TRACKER_ACTION_CONNECT = 0
TRACKER_ACTION_ANNOUNCE = 1
TRACKER_ACTION_SCRAPE = 2

MAX_INT32 = 2 ** 16 - 1

UDP_TRACKER_INIT_CONNECTION_ID = 0x41727101980
UDP_TRACKER_RECHECK_INTERVAL = 15
UDP_TRACKER_MAX_RETRIES = 8

HTTP_TRACKER_RECHECK_INTERVAL = 60
HTTP_TRACKER_MAX_RETRIES = 0

DHT_TRACKER_RECHECK_INTERVAL = 60
DHT_TRACKER_MAX_RETRIES = 8

MAX_TRACKER_MULTI_SCRAPE = 74


def create_tracker_session(tracker_url, timeout, socket_manager):
    """
    Creates a tracker session with the given tracker URL.
    :param tracker_url: The given tracker URL.
    :param timeout: The timeout for the session.
    :return: The tracker session.
    """
    tracker_type, tracker_address, announce_page = parse_tracker_url(tracker_url)

    if tracker_type == u'udp':
        return UdpTrackerSession(tracker_url, tracker_address, announce_page, timeout, socket_manager)
    else:
        return HttpTrackerSession(tracker_url, tracker_address, announce_page, timeout)


class TrackerSession(TaskManager):
    __meta__ = ABCMeta

    def __init__(self, tracker_type, tracker_url, tracker_address, announce_page, timeout):
        super(TrackerSession, self).__init__()

        self._logger = logging.getLogger(self.__class__.__name__)
        # tracker type in lowercase
        self._tracker_type = tracker_type
        self._tracker_url = tracker_url
        self._tracker_address = tracker_address
        # if this is a nonempty string it starts with '/'.
        self._announce_page = announce_page

        self._infohash_list = []
        self.result_deferred = None

        self._retries = 0
        self.timeout = timeout

        self._last_contact = None

        # some flags
        self._is_initiated = False  # you cannot add requests to a session if it has been initiated
        self._is_finished = False
        self._is_failed = False
        self._is_timed_out = False

    def __str__(self):
        return "Tracker[%s, %s]" % (self._tracker_type, self._tracker_url)

    def __unicode__(self):
        return u"Tracker[%s, %s]" % (self._tracker_type, self._tracker_url)

    @inlineCallbacks
    def cleanup(self):
        """
        Sets the _infohash_list to None and returns a deferred that has succeeded.
        :return: A deferred that succeeds immediately.
        """
        yield self.wait_for_deferred_tasks()

        self.shutdown_task_manager()
        self._infohash_list = None

    def can_add_request(self):
        """
        Checks if we still can add requests to this session.
        :return: True or False.
        """

        #TODO(ardhi) : quickfix for etree.org can't handle multiple infohash in single call
        etree_condition = "etree" not in self.tracker_url

        return not self._is_initiated and len(self._infohash_list) < MAX_TRACKER_MULTI_SCRAPE and etree_condition

    def has_infohash(self, infohash):
        return infohash in self._infohash_list

    def add_infohash(self, infohash):
        """
        Adds a infohash into this session.
        :param infohash: The infohash to be added.
        """
        assert not self._is_initiated, u"Must not add request to an initiated session."
        assert not self.has_infohash(infohash), u"Must not add duplicate requests"
        self._infohash_list.append(infohash)

    @abstractmethod
    def connect_to_tracker(self):
        """Does some work when a connection has been established."""
        pass

    @abstractproperty
    def max_retries(self):
        """Number of retries before a session is marked as failed."""
        pass

    @abstractproperty
    def retry_interval(self):
        """Interval between retries."""
        pass

    @property
    def tracker_type(self):
        return self._tracker_type

    @property
    def tracker_url(self):
        return self._tracker_url

    @property
    def infohash_list(self):
        return self._infohash_list

    @property
    def last_contact(self):
        return self._last_contact

    @property
    def retries(self):
        return self._retries

    def increase_retries(self):
        self._retries += 1

    @property
    def is_initiated(self):
        return self._is_initiated

    @property
    def is_finished(self):
        return self._is_finished

    @property
    def is_failed(self):
        return self._is_failed

    @property
    def is_timed_out(self):
        return self._is_timed_out


class HttpTrackerSession(TrackerSession):
    def __init__(self, tracker_url, tracker_address, announce_page, timeout):
        super(HttpTrackerSession, self).__init__(u'http', tracker_url, tracker_address, announce_page, timeout)
        self._header_buffer = None
        self._message_buffer = None
        self._content_encoding = None
        self._content_length = None
        self._received_length = None
        self.result_deferred = None
        self.request = None
        self._connection_pool = HTTPConnectionPool(reactor, False)

    def max_retries(self):
        """
        Returns the max amount of retries allowed for this session.
        :return: The maximum amount of retries.
        """
        return HTTP_TRACKER_MAX_RETRIES

    def retry_interval(self):
        """
        Returns the interval one has to wait before retrying to connect.
        :return: The interval before retrying.
        """
        return HTTP_TRACKER_RECHECK_INTERVAL

    def connect_to_tracker(self):
        # create the HTTP GET message
        # Note: some trackers have strange URLs, e.g.,
        #       http://moviezone.ws/announce.php?passkey=8ae51c4b47d3e7d0774a720fa511cc2a
        #       which has some sort of 'key' as parameter, so we need to use the add_url_params
        #       utility function to handle such cases.

        url = add_url_params("http://%s:%s%s" %
                             (self._tracker_address[0], self._tracker_address[1],
                              self._announce_page.replace(u'announce', u'scrape')),
                             {"info_hash": self._infohash_list})

        # no more requests can be appended to this session
        self._is_initiated = True
        self._last_contact = int(time.time())

        agent = RedirectAgent(Agent(reactor, connectTimeout=self.timeout, pool=self._connection_pool))
        try:
            self.request = self.register_task("request", agent.request('GET', bytes(url)))
            self.request.addCallback(self.on_response)
            self.request.addErrback(self.on_error)

            self._logger.debug(u"%s HTTP SCRAPE message sent: %s", self, url)

            # Return deferred that will evaluate when the whole chain is done.
            self.result_deferred = self.register_task("result", Deferred(canceller=self._on_cancel))

        except UnicodeEncodeError as e:
            self.result_deferred = defer.fail(e)

        return self.result_deferred

    def on_error(self, failure):
        """
        Handles the case of an error during the request.
        :param failure: The failure object that is thrown by a deferred.
        """
        self._logger.info("Error when querying http tracker: %s %s", str(failure), self.tracker_url)
        self.failed(msg=failure.getErrorMessage())

    def on_response(self, response):
        # Check if this one was OK.
        if response.code != 200:
            # error response code
            self._logger.warning(u"%s HTTP SCRAPE error response code [%s, %s]", self, response.code, response.phrase)
            self.failed(msg="error code %s" % response.code)
            return

        # All ok, parse the body
        self.register_task("parse_body", readBody(response).addCallbacks(self._process_scrape_response, self.on_error))

    def _on_cancel(self, a):
        """
        :param _: The deferred which we ignore.
        This function handles the scenario of the session prematurely being cleaned up,
        most likely due to a shutdown.
        This function only should be called by the result_deferred.
        """
        self._logger.info(
            "The result deferred of this HTTP tracker session is being cancelled due to a session cleanup. HTTP url: %s",
            self.tracker_url)

    def failed(self, msg=None):
        """
        This method handles everything that needs to be done when one step
        in the session has failed and thus no data can be obtained.
        """
        self._is_failed = True
        if self.result_deferred:
            result_msg = "HTTP tracker failed for url %s" % self._tracker_url
            if msg:
                result_msg += " (error: %s)" % unicode(msg, errors='replace')
            self.result_deferred.errback(ValueError(result_msg))

    def _process_scrape_response(self, body):
        """
        This function handles the response body of a HTTP tracker,
        parsing the results.
        """
        # parse the retrieved results
        if body is None:
            self.failed(msg="no response body")
            return

        response_dict = bdecode(body)
        if response_dict is None:
            self.failed(msg="no valid response")
            return

        response_list = []

        unprocessed_infohash_list = self._infohash_list[:]
        if 'files' in response_dict and isinstance(response_dict['files'], dict):
            for infohash in response_dict['files']:
                complete = response_dict['files'][infohash].get('complete', 0)
                incomplete = response_dict['files'][infohash].get('incomplete', 0)

                # Sow complete as seeders. "complete: number of peers with the entire file, i.e. seeders (integer)"
                #  - https://wiki.theory.org/BitTorrentSpecification#Tracker_.27scrape.27_Convention
                seeders = complete
                leechers = incomplete

                # Store the information in the dictionary
                response_list.append({'infohash': infohash.encode('hex'), 'seeders': seeders, 'leechers': leechers})

                # remove this infohash in the infohash list of this session
                if infohash in unprocessed_infohash_list:
                    unprocessed_infohash_list.remove(infohash)

        elif 'failure reason' in response_dict:
            self._logger.info(u"%s Failure as reported by tracker [%s]", self, repr(response_dict['failure reason']))
            self.failed(msg=repr(response_dict['failure reason']))
            return

        # handle the infohashes with no result (seeders/leechers = 0/0)
        for infohash in unprocessed_infohash_list:
            response_list.append({'infohash': infohash.encode('hex'), 'seeders': 0, 'leechers': 0})

        self._is_finished = True
        self.result_deferred.callback({self.tracker_url: response_list})

    @inlineCallbacks
    def cleanup(self):
        """
        Cleans the session by cancelling all deferreds and closing sockets.
        :return: A deferred that fires once the cleanup is done.
        """
        yield self._connection_pool.closeCachedConnections()
        yield super(HttpTrackerSession, self).cleanup()
        self.request = None

        self.result_deferred = None


class UdpSocketManager(DatagramProtocol):
    """
    The UdpSocketManager ensures that the network packets are forwarded to the right UdpTrackerSession.
    """

    def __init__(self):
        self._logger = logging.getLogger(self.__class__.__name__)
        self.tracker_sessions = {}

    def send_request(self, data, tracker_session):
        self.tracker_sessions[tracker_session.transaction_id] = tracker_session
        self.transport.write(data, (tracker_session.ip_address, tracker_session.port))

    def datagramReceived(self, data, _):
        # Find the tracker session and give it the data
        transaction_id = struct.unpack_from('!i', data, 4)[0]
        if transaction_id in self.tracker_sessions:
            self.tracker_sessions.pop(transaction_id).handle_response(data)


class UdpTrackerSession(TrackerSession):
    """
    The UDPTrackerSession makes a connection with a UDP tracker and queries
    seeders and leechers for one or more infohashes. It handles the message serialization
    and communication with the torrent checker by making use of Deferred (asynchronously).
    """

    # A list of transaction IDs that have been used in order to avoid conflict.
    _active_session_dict = dict()
    reactor = reactor

    def __init__(self, tracker_url, tracker_address, announce_page, timeout, socket_mgr):
        super(UdpTrackerSession, self).__init__(u'udp', tracker_url, tracker_address, announce_page, timeout)

        self._logger.setLevel(logging.INFO)
        self._connection_id = 0
        self.transaction_id = 0
        self.port = tracker_address[1]
        self.ip_address = None
        self.expect_connection_response = True
        self.socket_mgr = socket_mgr
        self.ip_resolve_deferred = None

        # prepare connection message
        self._connection_id = UDP_TRACKER_INIT_CONNECTION_ID
        self.action = TRACKER_ACTION_CONNECT
        self.generate_transaction_id()

        self.timeout_call = self.reactor.callLater(self.timeout, self.failed) if self.timeout != 0 else None

    def on_error(self, failure):
        """
        Handles the case when resolving an ip address fails.
        :param failure: The failure object thrown by the deferred.
        """
        self._logger.info("Error when querying UDP tracker: %s %s", str(failure), self.tracker_url)
        self.failed(msg=failure.getErrorMessage())

    def _on_cancel(self, _):
        """
        :param _: The deferred which we ignore.
        This function handles the scenario of the session prematurely being cleaned up,
        most likely due to a shutdown.
        This function only should be called by the result_deferred.
        """
        self._logger.info(
            "The result deferred of this UDP tracker session is being cancelled due to a session cleanup. UDP url: %s",
            self.tracker_url)

    def on_ip_address_resolved(self, ip_address, start_scraper=True):
        """
        Called when a hostname has been resolved to an ip address.
        Constructs a scraper and opens a UDP port to listen on.
        Removes an old scraper if present.
        :param ip_address: The ip address that matches the hostname of the tracker_url.
        :param start_scraper: Whether we should start the scraper immediately.
        """
        self.ip_address = ip_address
        self.connect()

    def failed(self, msg=None):
        """
        This method handles everything that needs to be done when one step
        in the session has failed and thus no data can be obtained.
        """
        if self.result_deferred and not self._is_failed:
            result_msg = "UDP tracker failed for url %s" % self._tracker_url
            if msg:
                result_msg += " (error: %s)" % unicode(msg, errors='replace')
            self.result_deferred.errback(ValueError(result_msg))

        self._is_failed = True

    def generate_transaction_id(self):
        """
        Generates a unique transaction id and stores this in the _active_session_dict set.
        """
        while True:
            # make sure there is no duplicated transaction IDs
            transaction_id = random.randint(0, MAX_INT32)
            if transaction_id not in UdpTrackerSession._active_session_dict.items():
                UdpTrackerSession._active_session_dict[self] = transaction_id
                self.transaction_id = transaction_id
                break

    @staticmethod
    def remove_transaction_id(session):
        """
        Removes an session and its corresponding id from the _active_session_dict set.
        :param session: The session that needs to be removed from the set.
        """
        if session in UdpTrackerSession._active_session_dict:
            del UdpTrackerSession._active_session_dict[session]

    @inlineCallbacks
    def cleanup(self):
        """
        Cleans the session by cancelling all deferreds and closing sockets.
        :return: A deferred that fires once the cleanup is done.
        """
        yield super(UdpTrackerSession, self).cleanup()
        UdpTrackerSession.remove_transaction_id(self)
        # Cleanup deferred that fires when everything has been cleaned
        # Cancel the resolving ip deferred.
        self.ip_resolve_deferred = None

        self.result_deferred = None

        if self.timeout_call and self.timeout_call.active():
            self.timeout_call.cancel()

    def max_retries(self):
        """
        Returns the max amount of retries allowed for this session.
        :return: The maximum amount of retries.
        """
        return UDP_TRACKER_MAX_RETRIES

    def retry_interval(self):
        """
        Returns the time one has to wait until retrying the connection again.
        Increases exponentially with the number of retries.
        :return: The interval one has to wait before retrying the connection.
        """
        return UDP_TRACKER_RECHECK_INTERVAL * (2 ** self._retries)

    def connect_to_tracker(self):
        """
        Connects to the tracker and starts querying for seed and leech data.
        :return: A deferred that will fire with a dictionary containing seed/leech information per infohash
        """
        # no more requests can be appended to this session
        self._is_initiated = True

        # clean old deferreds if present
        self.cancel_pending_task("result")
        self.cancel_pending_task("resolve")

        # Resolve the hostname to an IP address if not done already
        self.ip_resolve_deferred = self.register_task("resolve", reactor.resolve(self._tracker_address[0]))
        self.ip_resolve_deferred.addCallbacks(self.on_ip_address_resolved, self.on_error)

        self._last_contact = int(time.time())

        self.result_deferred = Deferred(self._on_cancel)
        return self.result_deferred

    def connect(self):
        """
        Creates a connection message and calls the socket manager to send it.
        """
        if not self.socket_mgr.transport:
            self.failed(msg="UDP socket transport not ready")
            return

        # Initiate the connection
        message = struct.pack('!qii', self._connection_id, self.action, self.transaction_id)
        self.socket_mgr.send_request(message, self)

    def handle_response(self, response):
        if self.is_failed:
            return

        if self.expect_connection_response:
            if self.timeout_call and self.timeout_call.active():
                self.timeout_call.cancel()

            self.handle_connection_response(response)
            self.expect_connection_response = False
        else:
            self.handle_scrape_response(response)

    def handle_connection_response(self, response):
        """
        Handles the connection response from the UDP tracker and queries
        it immediately for seed/leech data per infohash
        :param response: The connection response from the UDP tracker
        """
        # check message size
        if len(response) < 16:
            self._logger.error(u"%s Invalid response for UDP CONNECT: %s", self, repr(response))
            self.failed(msg="invalid response size")
            return

        # check the response
        action, transaction_id = struct.unpack_from('!ii', response, 0)
        if action != self.action or transaction_id != self.transaction_id:
            # get error message
            errmsg_length = len(response) - 8
            error_message = struct.unpack_from('!' + str(errmsg_length) + 's', response, 8)

            self._logger.info(u"%s Error response for UDP CONNECT [%s]: %s",
                              self, repr(response), repr(error_message))
            self.failed(msg=''.join(error_message))
            return

        # update action and IDs
        self._connection_id = struct.unpack_from('!q', response, 8)[0]
        self.action = TRACKER_ACTION_SCRAPE
        self.generate_transaction_id()

        # pack and send the message
        fmt = '!qii' + ('20s' * len(self._infohash_list))
        message = struct.pack(fmt, self._connection_id, self.action, self.transaction_id, *self._infohash_list)

        # Send the scrape message
        self.socket_mgr.send_request(message, self)

        self._last_contact = int(time.time())

    def handle_scrape_response(self, response):
        """
        Handles the scrape response from the UDP tracker.
        :param response: The response from the UDP tracker
        """
        # check message size
        if len(response) < 8:
            self._logger.info(u"%s Invalid response for UDP SCRAPE: %s", self, repr(response))
            self.failed("invalid message size")
            return

        # check response
        action, transaction_id = struct.unpack_from('!ii', response, 0)
        if action != self.action or transaction_id != self.transaction_id:
            # get error message
            errmsg_length = len(response) - 8
            error_message = struct.unpack_from('!' + str(errmsg_length) + 's', response, 8)

            self._logger.info(u"%s Error response for UDP SCRAPE: [%s] [%s]",
                              self, repr(response), repr(error_message))
            self.failed(msg=''.join(error_message))
            return

        # get results
        if len(response) - 8 != len(self._infohash_list) * 12:
            self._logger.info(u"%s UDP SCRAPE response mismatch: %s", self, len(response))
            self.failed(msg="invalid response size")
            return

        offset = 8

        response_list = []

        for infohash in self._infohash_list:
            complete, _downloaded, incomplete = struct.unpack_from('!iii', response, offset)
            offset += 12

            # Store the information in the hash dict to be returned.
            # Sow complete as seeders. "complete: number of peers with the entire file, i.e. seeders (integer)"
            #  - https://wiki.theory.org/BitTorrentSpecification#Tracker_.27scrape.27_Convention
            response_list.append({'infohash': infohash.encode('hex'), 'seeders': complete, 'leechers': incomplete})

        # close this socket and remove its transaction ID from the list
        UdpTrackerSession.remove_transaction_id(self)
        self._is_finished = True

        self.result_deferred.callback({self.tracker_url: response_list})


class FakeDHTSession(TrackerSession):
    """
    Fake TrackerSession that manages DHT requests
    """

    def __init__(self, session, infohash, timeout):
        super(FakeDHTSession, self).__init__(u'DHT', u'DHT', u'DHT', u'DHT', timeout)

        self.result_deferred = Deferred()
        self.infohash = infohash
        self._session = session

    def cleanup(self):
        """
        Cleans the session by cancelling all deferreds and closing sockets.
        :return: A deferred that fires once the cleanup is done.
        """
        self._infohash_list = None
        self._session = None
        # Return a defer that immediately calls its callback
        return defer.succeed(None)

    def can_add_request(self):
        """
        Returns whether or not this session can accept additional infohashes.
        :return:
        """
        return True

    def add_infohash(self, infohash):
        """
        This function adds a infohash to the request list.
        :param infohash: The infohash to be added.
        """
        self.infohash = infohash

    def connect_to_tracker(self):
        """
        Fakely connects to a tracker.
        :return: A deferred with a callback containing an empty dictionary.
        """
        @call_on_reactor_thread
        def on_metainfo_received(metainfo):
            self.result_deferred.callback({'DHT': [{'infohash': self.infohash.encode('hex'),
                                                    'seeders': metainfo['seeders'], 'leechers': metainfo['leechers']}]})

        @call_on_reactor_thread
        def on_metainfo_timeout(_):
            self.result_deferred.errback(Failure(RuntimeError("DHT timeout")))

        if self._session:
            self._session.lm.ltmgr.get_metainfo(self.infohash, callback=on_metainfo_received,
                                                timeout_callback=on_metainfo_timeout, timeout=self.timeout)

        return self.result_deferred

    @property
    def max_retries(self):
        """
        Returns the max amount of retries allowed for this session.
        :return: The maximum amount of retries.
        """
        return DHT_TRACKER_MAX_RETRIES

    @property
    def retry_interval(self):
        """
        Returns the interval one has to wait before retrying to connect.
        :return: The interval before retrying.
        """
        return DHT_TRACKER_RECHECK_INTERVAL

    @property
    def last_contact(self):
        # we never want this session to be cleaned up as it's faker than a 4 eur bill.
        return time.time()
