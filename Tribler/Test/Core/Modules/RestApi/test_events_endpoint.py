import json
from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.internet.protocol import Protocol
from twisted.web.client import Agent
from twisted.web.http_headers import Headers
from Tribler.Core.Modules.restapi import events_endpoint as events_endpoint_file
from Tribler.Core.Utilities.twisted_thread import deferred
from Tribler.Core.simpledefs import SIGNAL_CHANNEL, SIGNAL_ON_SEARCH_RESULTS, SIGNAL_TORRENT, NTFY_UPGRADER, \
    NTFY_STARTED, NTFY_FINISHED, NTFY_UPGRADER_TICK, NTFY_WATCH_FOLDER_CORRUPT_TORRENT, NTFY_INSERT, NTFY_NEW_VERSION, \
    NTFY_CHANNEL, NTFY_DISCOVERED, NTFY_TORRENT
from Tribler.Core.version import version_id
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest


class EventDataProtocol(Protocol):
    """
    This class is responsible for reading the data received over the event socket.
    """
    def __init__(self, messages_to_wait_for, finished, response):
        self.json_buffer = []
        self.messages_to_wait_for = messages_to_wait_for + 1  # The first event message is always events_start
        self.finished = finished
        self.response = response

    def dataReceived(self, data):
        self.json_buffer.append(json.loads(data))
        self.messages_to_wait_for -= 1
        if self.messages_to_wait_for == 0:
            self.finished.callback(self.json_buffer[1:])
            self.response.connectionLost(self)


class TestEventsEndpoint(AbstractApiTest):

    def setUp(self, autoload_discovery=True):
        super(TestEventsEndpoint, self).setUp(autoload_discovery=autoload_discovery)
        self.events_deferred = Deferred()
        self.socket_open_deferred = self.tribler_started_deferred.addCallback(self.open_events_socket)
        self.messages_to_wait_for = 0
        events_endpoint_file.MAX_EVENTS_BUFFER_SIZE = 100

    def on_event_socket_opened(self, response):
        response.deliverBody(EventDataProtocol(self.messages_to_wait_for, self.events_deferred, response))

    def open_events_socket(self, _):
        agent = Agent(reactor)
        return agent.request('GET', 'http://localhost:%s/events' % self.session.get_http_api_port(),
                             Headers({'User-Agent': ['Tribler ' + version_id]}), None)\
            .addCallback(self.on_event_socket_opened)

    @deferred(timeout=10)
    def test_events_buffer(self):
        """
        Testing whether we still receive messages that are in the buffer before the event connection is opened
        """
        def verify_delayed_message(results):
            self.assertEqual(len(results), 1)

        events_endpoint_file.MAX_EVENTS_BUFFER_SIZE = 1

        events_endpoint = self.session.lm.api_manager.root_endpoint.events_endpoint
        self.session.lm.api_manager.root_endpoint.events_endpoint.start_new_query()
        results_dict = {"keywords": ["test"], "result_list": [('a',) * 10]}
        events_endpoint.on_search_results_channels(None, None, None, results_dict)
        events_endpoint.on_search_results_torrents(None, None, None, results_dict)
        self.messages_to_wait_for = 1
        return self.events_deferred.addCallback(verify_delayed_message)

    @deferred(timeout=20)
    def test_search_results(self):
        """
        Testing whether the event endpoint returns search results when we have search results available
        """
        def verify_search_results(results):
            self.assertEqual(len(results), 3)

        self.messages_to_wait_for = 3

        def send_notifications(_):
            self.session.lm.api_manager.root_endpoint.events_endpoint.start_new_query()

            results_dict = {"keywords": ["test"], "result_list": [('a',) * 10]}
            self.session.notifier.notify(SIGNAL_CHANNEL, SIGNAL_ON_SEARCH_RESULTS, None, results_dict)
            self.session.notifier.notify(SIGNAL_TORRENT, SIGNAL_ON_SEARCH_RESULTS, None, results_dict)

        self.socket_open_deferred.addCallback(send_notifications)

        return self.events_deferred.addCallback(verify_search_results)

    def test_events(self):
        """
        Testing whether various events are coming through the events endpoints
        """
        self.messages_to_wait_for = 10

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
            self.session.notifier.notify(NTFY_TORRENT, NTFY_DISCOVERED, None, None)

        self.socket_open_deferred.addCallback(send_notifications)

        return self.events_deferred

    def test_family_filter_search(self):
        """
        Testing the family filter when searching for torrents and channels
        """
        events_endpoint = self.session.lm.api_manager.root_endpoint.events_endpoint

        channels = [['a', ] * 10, ['a', ] * 10]
        channels[0][2] = 'badterm'
        events_endpoint.on_search_results_channels(None, None, None, {"keywords": ["test"], "result_list": channels})
        self.assertEqual(len(events_endpoint.channel_cids_sent), 1)

        torrents = [['a', ] * 10, ['a', ] * 10]
        torrents[0][4] = 'xxx'
        events_endpoint.on_search_results_torrents(None, None, None, {"keywords": ["test"], "result_list": torrents})
        self.assertEqual(len(events_endpoint.infohashes_sent), 1)
