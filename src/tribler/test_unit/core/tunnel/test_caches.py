from asyncio import sleep
from unittest.mock import Mock

from ipv8.requestcache import RequestCache
from ipv8.test.base import TestBase

from tribler.core.tunnel.caches import HTTPRequestCache
from tribler.core.tunnel.payload import HTTPResponsePayload


class TestHTTPRequestCache(TestBase):
    """
    Tests for the HTTPRequestCache cache.
    """

    def setUp(self) -> None:
        """
        Create a new request cache.
        """
        self.request_cache = RequestCache()

    async def tearDown(self) -> None:
        """
        Destroy the cache.
        """
        await self.request_cache.shutdown()
        await super().tearDown()

    async def test_timeout_response_future(self) -> None:
        """
        Test if a HTTPRequestCache sets its response future to a value of None on timeout.
        """
        with self.request_cache.passthrough():
            cache = self.request_cache.add(HTTPRequestCache(Mock(request_cache=self.request_cache), 0))
            response_future = cache.response_future
            await sleep(0)

        self.assertIsNone(await response_future)
        self.assertFalse(self.request_cache.has(cache.prefix, cache.number))

    async def test_callback_response_future_one(self) -> None:
        """
        Test if a HTTPRequestCache completed with one response sets the value of its response future.
        """
        response = HTTPResponsePayload(0, 0, 0, 1, b"request")

        cache = self.request_cache.add(HTTPRequestCache(Mock(request_cache=self.request_cache), 0))
        added = cache.add_response(response)
        await sleep(0)

        self.assertTrue(added)
        self.assertEqual(response.response, await cache.response_future)

    async def test_callback_response_future_two(self) -> None:
        """
        Test if a HTTPRequestCache completed with two responses sets the value of its response future.
        """
        response1 = HTTPResponsePayload(0, 0, 0, 2, b"[first half]")
        response2 = HTTPResponsePayload(0, 1, 1, 2, b"[second half]")

        cache = self.request_cache.add(HTTPRequestCache(Mock(request_cache=self.request_cache), 0))
        completed = cache.add_response(response1)
        added = cache.add_response(response2)
        await sleep(0)

        self.assertFalse(completed)
        self.assertTrue(added)
        self.assertEqual(response1.response + response2.response, await cache.response_future)
