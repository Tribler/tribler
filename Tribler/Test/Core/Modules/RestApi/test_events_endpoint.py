import json
import logging
from twisted.internet import reactor
from twisted.internet.defer import Deferred, inlineCallbacks
from twisted.internet.protocol import Protocol
from twisted.internet.task import deferLater
from twisted.web.client import Agent, HTTPConnectionPool
from twisted.web.http_headers import Headers

from Tribler.Core.simpledefs import SIGNAL_CHANNEL, SIGNAL_ON_SEARCH_RESULTS, SIGNAL_TORRENT, NTFY_UPGRADER, \
    NTFY_STARTED, NTFY_FINISHED, NTFY_UPGRADER_TICK, NTFY_WATCH_FOLDER_CORRUPT_TORRENT, NTFY_INSERT, NTFY_NEW_VERSION, \
    NTFY_CHANNEL, NTFY_DISCOVERED, NTFY_TORRENT, NTFY_ERROR, NTFY_DELETE, NTFY_MARKET_ON_ASK, NTFY_UPDATE, \
    NTFY_MARKET_ON_BID, NTFY_MARKET_ON_ASK_TIMEOUT, NTFY_MARKET_ON_BID_TIMEOUT, NTFY_MARKET_ON_TRANSACTION_COMPLETE, \
    NTFY_MARKET_ON_PAYMENT_RECEIVED, NTFY_MARKET_ON_PAYMENT_SENT
from Tribler.Core.version import version_id
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.twisted_thread import deferred
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class EventDataProtocol(Protocol):
    """
    This class is responsible for reading the data received over the event socket.
    """
    def __init__(self, messages_to_wait_for, finished, response):
        self.json_buffer = []
        self._logger = logging.getLogger(self.__class__.__name__)
        self.messages_to_wait_for = messages_to_wait_for + 1  # The first event message is always events_start
        self.finished = finished
        self.response = response

    def dataReceived(self, data):
        self._logger.info("Received data: %s" % data)
        self.json_buffer.append(json.loads(data))
        self.messages_to_wait_for -= 1
        if self.messages_to_wait_for == 0:
            self.response.loseConnection()

    def connectionLost(self, reason="done"):
        self.finished.callback(self.json_buffer[1:])


class TestEventsEndpoint(AbstractApiTest):

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self, autoload_discovery=True):
        yield super(TestEventsEndpoint, self).setUp(autoload_discovery=autoload_discovery)
        self.events_deferred = Deferred()
        self.connection_pool = HTTPConnectionPool(reactor, False)
        self.socket_open_deferred = self.tribler_started_deferred.addCallback(self.open_events_socket)
        self.messages_to_wait_for = 0

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def tearDown(self, annotate=True):
        yield self.close_connections()

        # Wait to make sure the HTTPChannel is closed, see https://twistedmatrix.com/trac/ticket/2447
        yield deferLater(reactor, 0.3, lambda: None)

        yield super(TestEventsEndpoint, self).tearDown(annotate=annotate)

    def on_event_socket_opened(self, response):
        response.deliverBody(EventDataProtocol(self.messages_to_wait_for, self.events_deferred, response))

    def open_events_socket(self, _):
        agent = Agent(reactor, pool=self.connection_pool)
        return agent.request('GET', 'http://localhost:%s/events' % self.session.config.get_http_api_port(),
                             Headers({'User-Agent': ['Tribler ' + version_id]}), None)\
            .addCallback(self.on_event_socket_opened)

    def close_connections(self):
        return self.connection_pool.closeCachedConnections()

    @deferred(timeout=20)
    def test_search_results(self):
        """
        Testing whether the event endpoint returns search results when we have search results available
        """
        def verify_search_results(results):
            self.assertEqual(len(results), 2)

        self.messages_to_wait_for = 2

        def send_notifications(_):
            self.session.lm.api_manager.root_endpoint.events_endpoint.start_new_query()

            results_dict = {"keywords": ["test"], "result_list": [('a',) * 10]}
            self.session.notifier.notify(SIGNAL_CHANNEL, SIGNAL_ON_SEARCH_RESULTS, None, results_dict)
            self.session.notifier.notify(SIGNAL_TORRENT, SIGNAL_ON_SEARCH_RESULTS, None, results_dict)

        self.socket_open_deferred.addCallback(send_notifications)

        return self.events_deferred.addCallback(verify_search_results)

    @deferred(timeout=20)
    def test_events(self):
        """
        Testing whether various events are coming through the events endpoints
        """
        self.messages_to_wait_for = 20

        def send_notifications(_):
            self.session.lm.api_manager.root_endpoint.events_endpoint.start_new_query()
            results_dict = {"keywords": ["test"], "result_list": [('a',) * 10]}
            self.session.notifier.notify(SIGNAL_TORRENT, SIGNAL_ON_SEARCH_RESULTS, None, results_dict)
            self.session.notifier.notify(SIGNAL_CHANNEL, SIGNAL_ON_SEARCH_RESULTS, None, results_dict)
            self.session.notifier.notify(NTFY_UPGRADER, NTFY_STARTED, None, None)
            self.session.notifier.notify(NTFY_UPGRADER_TICK, NTFY_STARTED, None, None)
            self.session.notifier.notify(NTFY_UPGRADER, NTFY_FINISHED, None, None)
            self.session.notifier.notify(NTFY_WATCH_FOLDER_CORRUPT_TORRENT, NTFY_INSERT, None, None)
            self.session.notifier.notify(NTFY_NEW_VERSION, NTFY_INSERT, None, None)
            self.session.notifier.notify(NTFY_CHANNEL, NTFY_DISCOVERED, None, None)
            self.session.notifier.notify(NTFY_TORRENT, NTFY_DISCOVERED, None, {'a': 'Invalid character \xa1'})
            self.session.notifier.notify(NTFY_TORRENT, NTFY_DELETE, None, {'a': 'b'})
            self.session.notifier.notify(NTFY_TORRENT, NTFY_FINISHED, 'a' * 10, None)
            self.session.notifier.notify(NTFY_TORRENT, NTFY_ERROR, 'a' * 10, 'This is an error message')
            self.session.notifier.notify(NTFY_MARKET_ON_ASK, NTFY_UPDATE, None, {'a': 'b'})
            self.session.notifier.notify(NTFY_MARKET_ON_BID, NTFY_UPDATE, None, {'a': 'b'})
            self.session.notifier.notify(NTFY_MARKET_ON_ASK_TIMEOUT, NTFY_UPDATE, None, {'a': 'b'})
            self.session.notifier.notify(NTFY_MARKET_ON_BID_TIMEOUT, NTFY_UPDATE, None, {'a': 'b'})
            self.session.notifier.notify(NTFY_MARKET_ON_TRANSACTION_COMPLETE, NTFY_UPDATE, None, {'a': 'b'})
            self.session.notifier.notify(NTFY_MARKET_ON_PAYMENT_RECEIVED, NTFY_UPDATE, None, {'a': 'b'})
            self.session.notifier.notify(NTFY_MARKET_ON_PAYMENT_SENT, NTFY_UPDATE, None, {'a': 'b'})
            self.session.lm.api_manager.root_endpoint.events_endpoint.on_tribler_exception("hi")

        self.socket_open_deferred.addCallback(send_notifications)

        return self.events_deferred

    @deferred(timeout=20)
    def test_family_filter_search(self):
        """
        Testing the family filter when searching for torrents and channels
        """
        self.messages_to_wait_for = 2

        def send_searches(_):
            events_endpoint = self.session.lm.api_manager.root_endpoint.events_endpoint

            channels = [['a', ] * 10, ['a', ] * 10]
            channels[0][2] = 'badterm'
            events_endpoint.on_search_results_channels(None, None, None, {"keywords": ["test"],
                                                                          "result_list": channels})
            self.assertEqual(len(events_endpoint.channel_cids_sent), 1)

            torrents = [['a', ] * 10, ['a', ] * 10]
            torrents[0][4] = 'xxx'
            events_endpoint.on_search_results_torrents(None, None, None, {"keywords": ["test"],
                                                                          "result_list": torrents})
            self.assertEqual(len(events_endpoint.infohashes_sent), 1)

        self.socket_open_deferred.addCallback(send_searches)

        return self.events_deferred
