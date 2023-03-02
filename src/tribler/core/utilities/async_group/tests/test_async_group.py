import asyncio
import gc
from asyncio import gather
from contextlib import suppress
from weakref import ref

import pytest
from _pytest.logging import LogCaptureFixture

from tribler.core.utilities.async_group.async_group import AsyncGroup
from tribler.core.utilities.async_group.exceptions import CanceledException


# pylint: disable=redefined-outer-name, protected-access

@pytest.fixture
async def group():
    # When test is just started, the global set of futures should be empty.
    # If not, they are the futures leaked from the previous test
    assert not AsyncGroup._global_futures

    g = AsyncGroup()

    yield g

    if not g._canceled:
        await g.cancel()

    if AsyncGroup._global_futures:
        # It is possible that after the group was canceled, some of its futures were canceled as well,
        # but their done_callbacks were not executed yet. Here we give these futures a chance to execute
        # their done_callbacks and remove themselves from the global set of futures
        await asyncio.sleep(0.01)

    # The test should not leave unfinished futures at the end
    assert not AsyncGroup._global_futures


async def void():
    ...


async def sleep_1s():
    await asyncio.sleep(1)


async def raise_exception():
    raise ValueError


async def test_add_task(group: AsyncGroup):
    task = group.add_task(void())

    assert len(group._futures) == 1
    assert task


async def test_add_task_when_cancelled(group: AsyncGroup):
    await group.cancel()

    with pytest.raises(CanceledException):
        group.add_task(void())


async def test_cancel(group: AsyncGroup):
    """Ensure that all active tasks have been cancelled"""
    group.add_task(void())
    group.add_task(sleep_1s())

    cancelled = await group.cancel()

    assert len(cancelled) == 2
    assert all(f.cancelled() for f in cancelled)


async def test_wait(group: AsyncGroup):
    """Ensure that awe can wait for the futures"""
    group.add_task(void())
    group.add_task(sleep_1s())

    await group.wait()
    assert not group._futures


async def test_wait_no_futures(group: AsyncGroup):
    """Ensure that awe can wait for the futures even there are no futures"""
    await group.wait()
    assert not group._futures


async def test_double_cancel(group: AsyncGroup):
    """Ensure that double call of cancel doesn't lead to any exception"""
    group.add_task(void())
    assert not group.cancelled

    assert len(await group.cancel()) == 1
    assert group.cancelled
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


async def test_del_error(group: AsyncGroup, caplog: LogCaptureFixture):
    """ In this test we add a single coroutine to the group and call __del__ before the coroutine is completed.

    The group should add an error message to a log.
    """
    group.add_task(void())
    group.__del__()
    assert f'AsyncGroup is destroying but 1 futures are active' in caplog.text


async def test_del_no_error(group: AsyncGroup, caplog: LogCaptureFixture):
    """ In this test we add a single coroutine to the group and call __del__ after the coroutine is completed.

    The group should not add an error message to a log.
    """
    group.add_task(void())
    await group.wait()
    group.__del__()
    assert f'AsyncGroup is destroying but 1 futures are active' not in caplog.text


async def test_gc_error(caplog: LogCaptureFixture):
    assert not AsyncGroup._global_futures

    async def infinite_loop():
        while True:
            await asyncio.sleep(1)

    task1 = infinite_loop()
    task2 = infinite_loop()

    group = AsyncGroup()
    group.add_task(task1)
    group.add_task(task2)
    assert len(AsyncGroup._global_futures) == 2

    group_ref = ref(group)
    del group

    gc.collect()
    assert group_ref() is None

    text = caplog.text
    assert 'AsyncGroup is destroying but 2 futures are active' in text

    await asyncio.sleep(0.01)
    assert not AsyncGroup._global_futures


async def test_group_fixture():
    # There should be no active futures before the test
    assert not AsyncGroup._global_futures

    # We want to test the `group` fixture itself. Pytest does not allow to call fixture functions directly,
    # so we access fixture implementation using a Pytest internal attribute for that
    group_fixture_iter = group.__pytest_wrapped__.obj()

    g: AsyncGroup
    async for g in group_fixture_iter:
        # this for-loop should iterate over the fixture generator exactly once

        # we add a task to the async group, and the task should be canceled during the fixture teardown
        g.add_task(void())

        # if you remove the following two lines from the fixture, the test should fail,
        # as the task cannot call its done_callback:
        # if AsyncGroup._global_futures:
        #     await asyncio.sleep(0.01)

        # a magical line, without it the test passes even if two lines from the fixture were removed
        await asyncio.sleep(0)

    # There should be no active futures after the test
    assert not AsyncGroup._global_futures
