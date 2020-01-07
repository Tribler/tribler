from asyncio import CancelledError, Future, ensure_future
from contextlib import suppress

from aiohttp import ClientSession

from ipv8.messaging.anonymization.tunnel import Circuit

from tribler_common.simpledefs import NTFY

from tribler_core.restapi.base_api_test import AbstractApiTest
from tribler_core.tests.tools.tools import timeout
from tribler_core.version import version_id


class TestEventsEndpoint(AbstractApiTest):

    async def setUp(self):
        await super(TestEventsEndpoint, self).setUp()
        self.connected_future = Future()
        self.events_future = Future()
        self.messages_to_wait_for = 0
        self.event_socket_task = ensure_future(self.open_events_socket())
        await self.connected_future

    async def tearDown(self):
        self.event_socket_task.cancel()
        with suppress(CancelledError):
            await self.event_socket_task

    async def open_events_socket(self):
        url = 'http://localhost:%s/events' % self.session.config.get_http_api_port()
        headers = {'User-Agent': 'Tribler ' + version_id}

        async with ClientSession() as session:
            async with session.get(url, headers=headers) as response:
                # The first event message is always events_start
                await response.content.readline()
                self.connected_future.set_result(None)
                while True:
                    await response.content.readline()
                    self.messages_to_wait_for -= 1
                    if self.messages_to_wait_for == 0:
                        self.events_future.set_result(None)
                        break

    @timeout(20)
    async def test_events(self):
        """
        Testing whether various events are coming through the events endpoints
        """
        # self.session.notifier.notify(NTFY_TORRENT, NTFY_DISCOVERED, None, {'a': 'Invalid character \xa1'})
        # self.session.notifier.notify(NTFY_TORRENT, NTFY_ERROR, b'a' * 10, 'This is an error message', False)
        testdata = {
            NTFY.CHANNEL_ENTITY_UPDATED: {"state": "Complete"},
            NTFY.UPGRADER_STARTED: None,
            NTFY.UPGRADER_TICK: None,
            NTFY.UPGRADER_DONE: None,
            NTFY.WATCH_FOLDER_CORRUPT_FILE: None,
            NTFY.TRIBLER_NEW_VERSION: None,
            NTFY.CHANNEL_DISCOVERED: None,
            NTFY.TORRENT_FINISHED: (b'a' * 10, None, False),
            NTFY.LOW_SPACE: {},
            NTFY.CREDIT_MINING_ERROR: {"message": "Some credit mining error"},
            NTFY.TUNNEL_REMOVE: (Circuit(1234, None), 'test'),
            NTFY.CHANNEL_SEARCH_RESULTS: {"query": "test", "results": []},
        }
        self.messages_to_wait_for = len(testdata)
        for subject, data in testdata.items():
            if data:
                self.session.notifier.notify(subject, *data)
            else:
                self.session.notifier.notify(subject)
        self.session.api_manager.root_endpoint.endpoints['/events'].on_tribler_exception("hi")
        await self.events_future
