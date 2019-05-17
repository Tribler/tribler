from __future__ import absolute_import

import logging

from twisted.internet import reactor
from twisted.internet.defer import Deferred, inlineCallbacks
from twisted.internet.protocol import Protocol
from twisted.internet.task import deferLater
from twisted.web.client import Agent, HTTPConnectionPool
from twisted.web.http_headers import Headers

import Tribler.Core.Utilities.json_util as json
from Tribler.Core.simpledefs import (
    NTFY_CHANNEL, NTFY_CHANNEL_ENTITY, NTFY_CREDIT_MINING, NTFY_DISCOVERED, NTFY_ERROR, NTFY_FINISHED, NTFY_INSERT,
    NTFY_MARKET_ON_ASK, NTFY_MARKET_ON_ASK_TIMEOUT, NTFY_MARKET_ON_BID, NTFY_MARKET_ON_BID_TIMEOUT,
    NTFY_MARKET_ON_PAYMENT_RECEIVED, NTFY_MARKET_ON_PAYMENT_SENT, NTFY_MARKET_ON_TRANSACTION_COMPLETE, NTFY_NEW_VERSION,
    NTFY_REMOVE, NTFY_STARTED, NTFY_TORRENT, NTFY_TUNNEL, NTFY_UPDATE, NTFY_UPGRADER, NTFY_UPGRADER_TICK,
    NTFY_WATCH_FOLDER_CORRUPT_TORRENT, SIGNAL_GIGACHANNEL_COMMUNITY, SIGNAL_LOW_SPACE, SIGNAL_ON_SEARCH_RESULTS,
    SIGNAL_RESOURCE_CHECK)
from Tribler.Core.version import version_id
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest
from Tribler.Test.tools import trial_timeout
from Tribler.pyipv8.ipv8.messaging.anonymization.tunnel import Circuit


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
        self.json_buffer.append(json.twisted_loads(data))
        self.messages_to_wait_for -= 1
        if self.messages_to_wait_for == 0:
            self.response.loseConnection()

    def connectionLost(self, reason="done"):
        self.finished.callback(self.json_buffer[1:])


class TestEventsEndpoint(AbstractApiTest):

    @inlineCallbacks
    def setUp(self):
        yield super(TestEventsEndpoint, self).setUp()
        self.events_deferred = Deferred()
        self.connection_pool = HTTPConnectionPool(reactor, False)
        self.socket_open_deferred = self.tribler_started_deferred.addCallback(self.open_events_socket)
        self.messages_to_wait_for = 0

    @inlineCallbacks
    def tearDown(self):
        yield self.close_connections()

        # Wait to make sure the HTTPChannel is closed, see https://twistedmatrix.com/trac/ticket/2447
        yield deferLater(reactor, 0.3, lambda: None)

        yield super(TestEventsEndpoint, self).tearDown()

    def on_event_socket_opened(self, response):
        response.deliverBody(EventDataProtocol(self.messages_to_wait_for, self.events_deferred, response))

    def open_events_socket(self, _):
        agent = Agent(reactor, pool=self.connection_pool)
        return agent.request(b'GET', 'http://localhost:%s/events' % self.session.config.get_http_api_port(),
                             Headers({'User-Agent': ['Tribler ' + version_id]}), None) \
            .addCallback(self.on_event_socket_opened)

    def close_connections(self):
        return self.connection_pool.closeCachedConnections()

    @trial_timeout(20)
    def test_events(self):
        """
        Testing whether various events are coming through the events endpoints
        """
        self.messages_to_wait_for = 21

        def send_notifications(_):
            self.session.notifier.notify(NTFY_CHANNEL_ENTITY, NTFY_UPDATE, None, {"state": "Complete"})
            self.session.notifier.notify(NTFY_UPGRADER_TICK, NTFY_STARTED, None, None)
            self.session.notifier.notify(NTFY_UPGRADER, NTFY_FINISHED, None, None)
            self.session.notifier.notify(NTFY_WATCH_FOLDER_CORRUPT_TORRENT, NTFY_INSERT, None, None)
            self.session.notifier.notify(NTFY_NEW_VERSION, NTFY_INSERT, None, None)
            self.session.notifier.notify(NTFY_CHANNEL, NTFY_DISCOVERED, None, None)
            self.session.notifier.notify(NTFY_TORRENT, NTFY_DISCOVERED, None, {'a': 'Invalid character \xa1'})
            self.session.notifier.notify(NTFY_TORRENT, NTFY_FINISHED, 'a' * 10, None, False)
            self.session.notifier.notify(NTFY_TORRENT, NTFY_ERROR, 'a' * 10, 'This is an error message', False)
            self.session.notifier.notify(NTFY_MARKET_ON_ASK, NTFY_UPDATE, None, {'a': 'b'})
            self.session.notifier.notify(NTFY_MARKET_ON_BID, NTFY_UPDATE, None, {'a': 'b'})
            self.session.notifier.notify(NTFY_MARKET_ON_ASK_TIMEOUT, NTFY_UPDATE, None, {'a': 'b'})
            self.session.notifier.notify(NTFY_MARKET_ON_BID_TIMEOUT, NTFY_UPDATE, None, {'a': 'b'})
            self.session.notifier.notify(NTFY_MARKET_ON_TRANSACTION_COMPLETE, NTFY_UPDATE, None, {'a': 'b'})
            self.session.notifier.notify(NTFY_MARKET_ON_PAYMENT_RECEIVED, NTFY_UPDATE, None, {'a': 'b'})
            self.session.notifier.notify(NTFY_MARKET_ON_PAYMENT_SENT, NTFY_UPDATE, None, {'a': 'b'})
            self.session.notifier.notify(SIGNAL_RESOURCE_CHECK, SIGNAL_LOW_SPACE, None, {})
            self.session.notifier.notify(NTFY_CREDIT_MINING, NTFY_ERROR, None, {"message": "Some credit mining error"})
            self.session.notifier.notify(NTFY_TUNNEL, NTFY_REMOVE, Circuit(1234, None), 'test')
            self.session.notifier.notify(SIGNAL_GIGACHANNEL_COMMUNITY, SIGNAL_ON_SEARCH_RESULTS, None,
                                         {"query": "test", "results": []})
            self.session.lm.api_manager.root_endpoint.events_endpoint.on_tribler_exception("hi")

        self.socket_open_deferred.addCallback(send_notifications)

        return self.events_deferred
