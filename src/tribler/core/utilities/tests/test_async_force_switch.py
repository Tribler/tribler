import asyncio
import time

import pytest

from tribler.core.utilities.async_force_switch import force_switch


@pytest.mark.looptime(False)
async def test_without_switch():
    # In this test, we reproduce the asyncio behavior where there's a possibility
    # to block the main thread if there's no blocking event in the coroutine.
    class EndOfTheTest(TimeoutError):
        """Exception to stop a test after 0.2 seconds."""

    start_time = time.time()

    async def any_non_blocking_coro():
        duration = time.time() - start_time
        if duration >= 0.2:
            # to prevent indefinite block of a thread, raise an exception after 2 seconds.
            raise EndOfTheTest
        # With this line ↓
        # await asyncio.sleep(0)
        # `asyncio.wait_for()` will work as expected, interrupting the execution of the coroutine after 0.1 sec.
        # Without this line, the main thread will be blocked indefinitely.

    async def a():
        while True:
            await any_non_blocking_coro()

    # We are waiting for the timeout, but coroutine a() will never be cancelled.
    with pytest.raises(EndOfTheTest):
        await asyncio.wait_for(a(), timeout=0.1)


@pytest.mark.looptime(False)
async def test_force_switch():
    # In this test, we show that by using the @force_switch decorator, the function any_non_blocking_coro
    # doesn't block the main thread and `asyncio.wait_for` works as expected.
    @force_switch
    async def any_non_blocking_coro():
        ...

    async def a():
        while True:
            await any_non_blocking_coro()

    with pytest.raises(asyncio.TimeoutError):
        await asyncio.wait_for(a(), timeout=0.1)
