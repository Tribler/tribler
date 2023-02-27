import asyncio
from contextlib import suppress

import pytest

from tribler.core.utilities.async_group.async_group import AsyncGroup


# pylint: disable=redefined-outer-name, protected-access

@pytest.fixture
async def group():
    g = AsyncGroup()

    yield g

    await g.cancel()


async def void():
    ...


async def sleep_1s():
    await asyncio.sleep(1)


async def raise_exception():
    raise ValueError


async def test_add_single_coro(group: AsyncGroup):
    tasks = group.add_task(
        void()
    )

    assert len(group._futures) == 1
    assert len(tasks) == 1


async def test_add_iterable(group: AsyncGroup):
    tasks = group.add_task(
        void(),
        void(),
        void()
    )

    assert len(group._futures) == 3
    assert len(tasks) == 3


async def test_cancel(group: AsyncGroup):
    """Ensure that all active tasks have been cancelled"""
    group.add_task(
        void(),
        sleep_1s()
    )

    cancelled = await group.cancel()

    assert len(cancelled) == 2
    assert all(f.cancelled() for f in cancelled)


async def test_wait(group: AsyncGroup):
    """Ensure that awe can wait for the futures"""
    group.add_task(
        void(),
        sleep_1s()
    )

    await group.wait()
    assert not group._futures


async def test_wait_no_futures(group: AsyncGroup):
    """Ensure that awe can wait for the futures even there are no futures"""
    await group.wait()
    assert not group._futures


async def test_double_cancel(group: AsyncGroup):
    """Ensure that double call of cancel doesn't lead to any exception"""

    group.add_task(
        void()
    )

    assert len(await group.cancel()) == 1
    assert len(await group.cancel()) == 0


async def test_cancel_completed_task(group: AsyncGroup):
    """Ensure that in case of mixed tasks only active tasks will be cancelled"""
    completed = [
        asyncio.create_task(void()),
        asyncio.create_task(void())
    ]

    await asyncio.gather(*completed)

    active = asyncio.create_task(void())
    group._futures = completed + [active]

    cancelled = await group.cancel()

    assert len(cancelled) == 1


async def test_auto_cleanup(group: AsyncGroup):
    """In this test we adds 100 coroutines of each type (void, sleep_1s, raise_exception)
    and wait for their execution.

    After all coroutines will be completed, `group._futures` should be zero.
    """
    functions = void, sleep_1s, raise_exception

    for f in functions:
        for _ in range(100):
            group.add_task(f())
    assert len(group._futures) == 300

    with suppress(ValueError):
        await asyncio.gather(*group._futures, return_exceptions=True)

    assert not group._futures
