from asyncio import sleep

from ipv8.requestcache import RequestCache
from ipv8.test.base import TestBase

from tribler.core.content_discovery.cache import SelectRequest


class TestSelectRequest(TestBase):
    """
    Tests for the SelectRequest cache.
    """

    async def test_timeout_no_cb(self) -> None:
        """
        Test if a SelectRequest can time out without a callback set.
        """
        request_cache = RequestCache()

        with request_cache.passthrough():
            cache = request_cache.add(SelectRequest(request_cache, "test", {}, None))
            await sleep(0)

        self.assertFalse(request_cache.has(cache.prefix, cache.number))

    async def test_timeout_with_cb(self) -> None:
        """
        Test if a SelectRequest can time out with a callback set.
        """
        request_cache = RequestCache()
        callback_values = []

        with request_cache.passthrough():
            cache = request_cache.add(SelectRequest(request_cache, "test", {}, None,
                                                    timeout_callback=callback_values.append))
            await sleep(0)

        self.assertFalse(request_cache.has(cache.prefix, cache.number))
        self.assertIn(cache, callback_values)
