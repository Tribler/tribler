from asyncio import CancelledError, Future, ensure_future
from contextlib import suppress

from aiohttp import ClientSession

from ipv8.messaging.anonymization.tunnel import Circuit

from tribler_common.simpledefs import (
    NTFY_CHANNEL,
    NTFY_CHANNEL_ENTITY,
    NTFY_CREDIT_MINING,
    NTFY_DISCOVERED,
    NTFY_ERROR,
    NTFY_FINISHED,
    NTFY_INSERT,
    NTFY_MARKET_ON_ASK,
    NTFY_MARKET_ON_ASK_TIMEOUT,
    NTFY_MARKET_ON_BID,
    NTFY_MARKET_ON_BID_TIMEOUT,
    NTFY_MARKET_ON_PAYMENT_RECEIVED,
    NTFY_MARKET_ON_PAYMENT_SENT,
    NTFY_MARKET_ON_TRANSACTION_COMPLETE,
    NTFY_NEW_VERSION,
    NTFY_REMOVE,
    NTFY_STARTED,
    NTFY_TORRENT,
    NTFY_TUNNEL,
    NTFY_UPDATE,
    NTFY_UPGRADER,
    NTFY_UPGRADER_TICK,
    NTFY_WATCH_FOLDER_CORRUPT_TORRENT,
    SIGNAL_GIGACHANNEL_COMMUNITY,
    SIGNAL_LOW_SPACE,
    SIGNAL_ON_SEARCH_RESULTS,
    SIGNAL_RESOURCE_CHECK,
)

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
        self.messages_to_wait_for = 21
        self.session.notifier.notify(NTFY_CHANNEL_ENTITY, NTFY_UPDATE, None, {"state": "Complete"})
        self.session.notifier.notify(NTFY_UPGRADER_TICK, NTFY_STARTED, None, None)
        self.session.notifier.notify(NTFY_UPGRADER, NTFY_FINISHED, None, None)
        self.session.notifier.notify(NTFY_WATCH_FOLDER_CORRUPT_TORRENT, NTFY_INSERT, None, None)
        self.session.notifier.notify(NTFY_NEW_VERSION, NTFY_INSERT, None, None)
        self.session.notifier.notify(NTFY_CHANNEL, NTFY_DISCOVERED, None, None)
        self.session.notifier.notify(NTFY_TORRENT, NTFY_DISCOVERED, None, {'a': 'Invalid character \xa1'})
        self.session.notifier.notify(NTFY_TORRENT, NTFY_FINISHED, b'a' * 10, None, False)
        self.session.notifier.notify(NTFY_TORRENT, NTFY_ERROR, b'a' * 10, 'This is an error message', False)
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
        self.session.api_manager.root_endpoint.endpoints['/events'].on_tribler_exception("hi")
        await self.events_future
