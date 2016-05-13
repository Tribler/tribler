import json
from twisted.internet import reactor
from twisted.internet.defer import Deferred
from twisted.internet.protocol import Protocol
from twisted.web.client import Agent
from twisted.web.http_headers import Headers
from Tribler.Core.Modules.restapi import events_endpoint
from Tribler.Core.Utilities.twisted_thread import deferred
from Tribler.Core.simpledefs import SIGNAL_CHANNEL, SIGNAL_ON_SEARCH_RESULTS, SIGNAL_TORRENT
from Tribler.Core.version import version_id
from Tribler.Test.Core.Modules.RestApi.base_api_test import AbstractApiTest


class EventDataProtocol(Protocol):
    """
    This class is responsible for reading the data received over the event socket.
    """
    def __init__(self, messages_to_wait_for, finished):
        self.json_buffer = []
        self.messages_to_wait_for = messages_to_wait_for + 1  # The first event message is always events_start
        self.finished = finished

    def dataReceived(self, data):
        self.json_buffer.append(json.loads(data))
        self.messages_to_wait_for -= 1
        if self.messages_to_wait_for == 0:
            self.finished.callback(self.json_buffer[1:])


class TestEventsEndpoint(AbstractApiTest):

    def __init__(self, *args, **kwargs):
        super(TestEventsEndpoint, self).__init__(*args, **kwargs)
        self.events_deferred = Deferred()

    def on_event_socket_opened(self, response):
        response.deliverBody(EventDataProtocol(self.messages_to_wait_for, self.events_deferred))

    def open_events_socket(self):
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
            self.assertEqual(results[0][u'type'], u'search_result_channel')
            self.assertTrue(results[0][u'result'])

        events_endpoint.MAX_EVENTS_BUFFER_SIZE = 1

        results_dict = {"keywords": ["test"], "result_list": [('a',) * 9]}
        self.session.notifier.use_pool = False
        self.session.notifier.notify(SIGNAL_TORRENT, SIGNAL_ON_SEARCH_RESULTS, None, results_dict)
        self.session.notifier.notify(SIGNAL_CHANNEL, SIGNAL_ON_SEARCH_RESULTS, None, results_dict)
        self.messages_to_wait_for = 1
        self.open_events_socket()
        return self.events_deferred.addCallback(verify_delayed_message)

    @deferred(timeout=10)
    def test_search_results(self):
        """
        Testing whether the event endpoint returns search results when we have search results available
        """
        def verify_search_results(results):
            self.assertEqual(results[0][u'type'], u'search_result_channel')
            self.assertEqual(results[1][u'type'], u'search_result_torrent')

            self.assertTrue(results[0][u'result'])
            self.assertTrue(results[1][u'result'])

        def create_search_results(_):
            results_dict = {"keywords": ["test"], "result_list": [('a',) * 9]}
            self.session.notifier.use_pool = False
            self.session.notifier.notify(SIGNAL_CHANNEL, SIGNAL_ON_SEARCH_RESULTS, None, results_dict)
            self.session.notifier.notify(SIGNAL_TORRENT, SIGNAL_ON_SEARCH_RESULTS, None, results_dict)

        self.messages_to_wait_for = 2
        self.open_events_socket().addCallback(create_search_results)
        return self.events_deferred.addCallback(verify_search_results)
