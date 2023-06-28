import asyncio
import logging
from asyncio import InvalidStateError
from unittest.mock import AsyncMock, Mock

import pytest

from tribler.core.components.ipv8.eva.exceptions import TimeoutException, TransferException
from tribler.core.components.ipv8.eva.protocol import blank
from tribler.core.components.ipv8.eva.settings import EVASettings
from tribler.core.components.ipv8.eva.transfer.base import Transfer
from tribler.core.utilities.async_group.async_group import AsyncGroup


# pylint: disable=redefined-outer-name, protected-access

@pytest.fixture
async def transfer():
    container = {}
    peer = Mock()
    protocol_task_group = AsyncGroup()
    transfer = Transfer(
        container=container,
        info=b'info',
        data_size=100,
        nonce=0,
        peer=peer,
        protocol_task_group=protocol_task_group,
        send_message=Mock(),
        on_complete=blank,
        on_error=blank,
        settings=EVASettings(block_size=2),
    )
    transfer.request = Mock()
    container[peer] = transfer
    yield transfer

    transfer.finish()
    await protocol_task_group.wait()


def test_update(transfer: Transfer):
    # In this test we ensure that `transfer.update` method sets `time.time` value
    # to `transfer.updated` property.
    transfer.loop.time = Mock(return_value=42)

    transfer.update()

    assert transfer.updated == 42


async def test_finish_double_call(transfer: Transfer):
    assert not transfer.finished

    # The first call of the finish method should process exception and result
    # and clean the container property
    transfer.finish()
    assert transfer.finished
    assert not transfer.container

    # The second call should do nothing. To check correctness we have to set any
    # value to transfer.container and ensure that it will not bt changed.
    transfer.container = 'any'
    transfer.finish()
    assert transfer.container == 'any'


async def test_release(transfer: Transfer):
    # In this test we ensure that `_release` method cleans all necessary fields
    container = transfer.container
    assert container

    transfer._release()

    assert transfer.finished
    assert not transfer.container
    assert not container


async def test_release_double_call(transfer: Transfer):
    # In this test we ensure that double call of the `_release` method doesn't
    # lead to any exception

    transfer._release()
    transfer._release()

    assert transfer.finished


async def test_start(transfer: Transfer):
    # In this test we ensure that after starting a transfer, it's `task_group`
    # is started and the transfer has been added to a container
    transfer.start()

    assert transfer.started
    assert transfer.peer in transfer.container
    assert len(transfer.task_group.futures) == 2


async def test_double_start(transfer: Transfer):
    # In this test we ensure that double call of `transfer.start` doesn't lead
    # to any exception
    transfer.start()
    transfer.start()

    assert transfer.started


async def test_finish_cancelled(transfer: Transfer):
    # In this test we ensure that calling the `finish` method with cancelled
    # transfer future doesn't lead to any exception
    transfer.future.cancel()

    transfer.finish(result=Mock())

    assert not transfer.finished


async def test_finish_with_result(transfer: Transfer):
    result = Mock()
    transfer.on_complete = AsyncMock()

    transfer.finish(result=result)
    await transfer.protocol_task_group.wait()

    assert transfer.finished
    assert transfer.future.result() == result
    assert transfer.on_complete.called_with(result)


async def test_finish_with_exception(transfer: Transfer):
    exception = TransferException(message='message', transfer=Mock())
    transfer.on_complete = AsyncMock()

    transfer.finish(exception=exception)
    await transfer.protocol_task_group.wait()

    assert transfer.finished
    assert transfer.future.exception() == exception
    assert transfer.on_complete.called_with(exception)


async def test_finish_with_exception_and_result(transfer: Transfer):
    exception = TransferException(message='message', transfer=Mock())

    with pytest.raises(InvalidStateError):
        transfer.finish(exception=exception, result=Mock())


async def test_terminate_by_timeout_task(transfer: Transfer):
    transfer.settings.termination.timeout = 0

    await transfer.terminate_by_timeout()

    assert transfer.finished
    assert transfer.future.done()
    assert isinstance(transfer.future.exception(), TimeoutException)


async def test_terminate_by_timeout_task_with_update(transfer: Transfer):
    # In this test we run two tasks concurrently:
    # 1. `update_transfer` task which updates transfer every 0.05 sec
    # 2. `terminate_by_timeout_task` task which terminates transfer after 0.1 seconds of idle

    # In the case that `terminate_by_timeout_task` works as expected, it will wait until
    # `update_transfer` finish it's work and then will terminate the transfer
    update_sleep_interval = 0.05
    transfer.settings.termination.timeout = 0.1
    transfer.update = Mock(wraps=transfer.update)
    logging.info(transfer)

    async def update_transfer():  # should process 0.2 sec in total
        for attempt in range(4):
            logging.debug(f'Sleep({attempt}) {update_sleep_interval}s...')
            await asyncio.sleep(update_sleep_interval)
            transfer.update()

    await asyncio.gather(
        update_transfer(),
        transfer.terminate_by_timeout()
    )

    assert transfer.update.call_count == 4
    assert transfer.finished
    assert transfer.future.done()
    assert isinstance(transfer.future.exception(), TimeoutException)


async def test_terminate_by_timeout_task_disable(transfer: Transfer):
    transfer.settings.termination.enabled = False

    await transfer.terminate_by_timeout()

    assert not transfer.finished
    assert not transfer.future.done()


async def test_terminate_by_timeout_task_finished(transfer: Transfer):
    transfer.settings.termination.timeout = 0
    transfer.finished = True

    await transfer.terminate_by_timeout()

    assert not transfer.future.done()


async def test_start_request_task(transfer: Transfer):
    transfer.settings.retransmission.interval = 0
    transfer.attempt = 3
    transfer.update = Mock(wrap=transfer.update)

    await transfer.start_request()

    assert transfer.update.call_count == 4  # 1 mandatory attempt and 3 re-transmit
    assert transfer.send_message.call_count == 4  # 1 mandatory attempt and 3 re-transmit


async def test_start_request_task_finished(transfer: Transfer):
    # In this test we will mark the transfer as finished during the first call of `send_message`
    # therefore a count of send attempts should be equal to `1`

    transfer.settings.retransmission.interval = 0

    def send_message(*_):
        transfer.finished = True

    transfer.send_message = Mock(wraps=send_message)

    await transfer.start_request()
    assert transfer.send_message.call_count == 1


async def test_start_request_task_start_request_received(transfer: Transfer):
    # In this test we will set `start_request_received` as `True` during the first call of `send_message`
    # therefore a count of send attempts should be equal to `1`

    transfer.settings.retransmission.interval = 0
    transfer.attempt = 3

    def send_message(*_):
        transfer.request_received = True

    transfer.send_message = Mock(wraps=send_message)

    await transfer.start_request()
    assert transfer.send_message.call_count == 1


async def test_format_attempt(transfer: Transfer):
    assert transfer._format_attempt(remains=3, maximum=3) == '0/3'
    assert transfer._format_attempt(remains=2, maximum=3) == '1/3'
    assert transfer._format_attempt(remains=1, maximum=3) == '2/3'
    assert transfer._format_attempt(remains=0, maximum=3) == '3/3'


async def test_remaining(transfer: Transfer):
    # Imagine that now time is `10` and transfer has been updated in `0`
    transfer.loop.time = Mock(return_value=10)
    transfer.updated = 0

    assert transfer._remaining(5) == -5
    assert transfer._remaining(10) == 0
    assert transfer._remaining(15) == 5
