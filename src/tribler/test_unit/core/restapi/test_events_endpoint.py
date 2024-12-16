from asyncio import Future, ensure_future, sleep

from aiohttp.abc import AbstractStreamWriter
from ipv8.test.base import TestBase
from ipv8.test.REST.rest_base import MockRequest
from multidict import CIMultiDict

from tribler.core.notifier import Notification, Notifier
from tribler.core.restapi.events_endpoint import EventsEndpoint


class GetEventsRequest(MockRequest):
    """
    A MockRequest that mimics GetEventsRequests.
    """

    def __init__(self, endpoint: EventsEndpoint, count: int = 1) -> None:
        """
        Create a new GetEventsRequest.
        """
        self.payload_writer = MockStreamWriter(endpoint, count=count)
        self._handler_waiter = Future()
        super().__init__("/api/events", payload_writer=self.payload_writer)

    def shutdown(self) -> None:
        """
        Mimic a shutdown.
        """
        self._handler_waiter.cancel()

    def finish_handler(self) -> None:
        """
        Mimic finishing a handler.
        """
        self._handler_waiter.set_result(None)


class MockStreamWriter(AbstractStreamWriter):
    """
    A streamwriter that closes the endpoint after a given number of writes.
    """

    def __init__(self, endpoint: EventsEndpoint, count: int = 1) -> None:
        """
        Create a new MockStreamWriter.
        """
        super().__init__()
        self.endpoint = endpoint
        self.count = count
        self.captured = []

    async def write(self, chunk: bytes) -> None:
        """
        Write a chunk and check if we should shut down the endpoint.
        """
        self.captured.append(chunk)
        self.count -= 1
        if self.count == 0:
            self.endpoint.shutdown_event.set()

    async def write_eof(self, chunk: bytes = b"") -> None:
        """
        Ignore EOFs.
        """

    async def drain(self) -> None:
        """
        Ignore drains.
        """

    def enable_compression(self, encoding: str = "deflate") -> None:
        """
        Ignore compression.
        """

    def enable_chunking(self) -> None:
        """
        Ignore chunking settings.
        """

    async def write_headers(self, status_line: str, headers: CIMultiDict[str]) -> None:
        """
        Ignore headers.
        """


class TestEventsEndpoint(TestBase):
    """
    Tests for the EventsEndpoint class.
    """

    def setUp(self) -> None:
        """
        Create an inert EventsEndpoint.
        """
        super().setUp()

        self.notifier = Notifier()
        self.endpoint = EventsEndpoint(self.notifier)

    async def tearDown(self) -> None:
        """
        Shut down the endpoint.
        """
        await self.endpoint.shutdown_task_manager()
        await super().tearDown()

    async def test_establish_connection(self) -> None:
        """
        Test if opening an events connection leads to an event start.
        """
        request = GetEventsRequest(self.endpoint, count=1)

        response = await self.endpoint.get_events(request)

        self.assertEqual(200, response.status)
        self.assertEqual((b'event: events_start\n'
                          b'data: {"public_key": "", "version": "git"}'
                          b'\n\n'), request.payload_writer.captured[0])

    async def test_establish_connection_with_error(self) -> None:
        """
        Test if opening an events connection with an error leads to an event start followed by the error.
        """
        self.endpoint.undelivered_error = ValueError("test message")
        request = GetEventsRequest(self.endpoint, count=2)

        response = await self.endpoint.get_events(request)

        self.assertEqual(200, response.status)
        self.assertEqual((b'event: tribler_exception\n'
                          b'data: {"error": "test message", "traceback": "ValueError: test message\\n"}'
                          b'\n\n'), request.payload_writer.captured[1])

    async def test_forward_error(self) -> None:
        """
        Test if errors are forwarded over the stream.
        """
        request = GetEventsRequest(self.endpoint, count=2)

        response_future = ensure_future(self.endpoint.get_events(request))
        await sleep(0)
        self.endpoint.on_tribler_exception(ValueError("test message"))
        response = await response_future

        self.assertEqual(200, response.status)
        self.assertIsNone(self.endpoint.undelivered_error)
        self.assertEqual((b'event: tribler_exception\n'
                          b'data: {"error": "test message", "traceback": "ValueError: test message\\n"}'
                          b'\n\n'), request.payload_writer.captured[1])

    async def test_error_before_connection(self) -> None:
        """
        Test if errors are stored as undelivered errors when no connection is available.
        """
        exception = ValueError("test message")
        self.endpoint.on_tribler_exception(exception)

        self.assertEqual(exception, self.endpoint.undelivered_error)

    async def test_send_event(self) -> None:
        """
        Test if event dicts can be sent.
        """
        request = GetEventsRequest(self.endpoint, count=2)

        response_future = ensure_future(self.endpoint.get_events(request))
        await sleep(0)
        self.endpoint.send_event({"topic": "message", "kwargs": {"key": "value"}})
        response = await response_future

        self.assertEqual(200, response.status)
        self.assertIsNone(self.endpoint.undelivered_error)
        self.assertEqual((b'event: message\n'
                          b'data: {"key": "value"}'
                          b'\n\n'), request.payload_writer.captured[1])

    async def test_send_event_illegal_chars(self) -> None:
        """
        Test if event dicts error out if they contain illegal characters.
        """
        request = GetEventsRequest(self.endpoint, count=2)

        response_future = ensure_future(self.endpoint.get_events(request))
        await sleep(0)
        self.endpoint.send_event({"topic": "message", "kwargs": {"something": b"\x80"}})
        response = await response_future

        self.assertEqual(200, response.status)
        self.assertIsNone(self.endpoint.undelivered_error)
        self.assertTrue(request.payload_writer.captured[1].startswith(
            b'event: tribler_exception\n'
            b'data: {"error": "Object of type bytes is not JSON serializable", "traceback": "'
        ))

    async def test_forward_notification(self) -> None:
        """
        Test if notifications are forwarded.
        """
        request = GetEventsRequest(self.endpoint, count=2)

        response_future = ensure_future(self.endpoint.get_events(request))
        await sleep(0)
        self.endpoint.on_notification(Notification.tribler_new_version, version="super cool version")
        response = await response_future

        self.assertEqual(200, response.status)
        self.assertIsNone(self.endpoint.undelivered_error)
        self.assertEqual((b'event: tribler_new_version\n'
                          b'data: {"version": "super cool version"}'
                          b'\n\n'), request.payload_writer.captured[1])

    async def test_no_forward_illegal_notification(self) -> None:
        """
        Test if notifications are only forwarded if they are in the topics_to_send_to_gui whitelist.
        """
        request = GetEventsRequest(self.endpoint, count=2)

        response_future = ensure_future(self.endpoint.get_events(request))
        await sleep(0)
        self.endpoint.on_notification(Notification.peer_disconnected, peer_id=b"\x00\x01")  # Should be dropped
        self.endpoint.on_notification(Notification.tribler_new_version, version="super cool version")  # Delivered
        response = await response_future

        self.assertEqual(200, response.status)
        self.assertIsNone(self.endpoint.undelivered_error)
        self.assertEqual((b'event: tribler_new_version\n'
                          b'data: {"version": "super cool version"}'
                          b'\n\n'), request.payload_writer.captured[1])

    async def test_shutdown_parent_before_event(self) -> None:
        """
        Test if a parent shutdown does not cause errors after handling a child.
        """
        request = GetEventsRequest(self.endpoint, count=3)  # Blocks until shutdown
        response_future = ensure_future(self.endpoint.get_events(request))

        request.shutdown()  # 1. The parent protocol is shut down
        self.endpoint.shutdown_event.set()  # 2. Tribler signals shutdown to the events endpoint
        response = await response_future
        request.finish_handler()  # 3. aiohttp behavior: finish the request handling

        self.assertEqual(200, response.status)
