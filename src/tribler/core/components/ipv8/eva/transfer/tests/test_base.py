import asyncio
from asyncio import InvalidStateError
from unittest.mock import AsyncMock, Mock, patch

import pytest

from tribler.core.components.ipv8.eva.exceptions import TimeoutException, TransferException
from tribler.core.components.ipv8.eva.settings import EVASettings
from tribler.core.components.ipv8.eva.transfer.base import Transfer


# pylint: disable=redefined-outer-name, protected-access

@pytest.fixture
def transfer() -> Transfer:
    peer = Mock()
    container = {}
    transfer = Transfer(container=container, info=b'info', data_size=100, nonce=0, on_complete=AsyncMock(), peer=peer,
                        settings=EVASettings(block_size=2))
    container[peer] = transfer
    return transfer


@patch('time.time', Mock(return_value=42))
def test_update(transfer: Transfer):
    transfer.update()

    assert transfer.updated == 42


def test_finish_double_call(transfer: Transfer):
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
    container = transfer.container
    assert container

    transfer._release()

    assert transfer.finished
    assert not transfer.container
    assert not container


async def test_release_double_call(transfer: Transfer):
    transfer._release()
    transfer._release()

    assert transfer.finished


async def test_finish_cancelled(transfer: Transfer):
    transfer.future.cancel()
    transfer.finish(result=Mock())
    await asyncio.sleep(0.1)  # sleep to process cancel callback
    assert transfer.finished


async def test_finish_with_result(transfer: Transfer):
    result = Mock()

    transfer.finish(result=result)

    assert transfer.finished
    assert transfer.future.result() == result
    assert transfer.on_complete.called_with(result)


async def test_finish_with_exception(transfer: Transfer):
    exception = TransferException(message='message', transfer=Mock())

    transfer.finish(exception=exception)

    assert transfer.finished
    assert transfer.future.exception() == exception
    assert transfer.on_complete.called_with(exception)


async def test_finish_with_exception_and_result(transfer: Transfer):
    exception = TransferException(message='message', transfer=Mock())

    with pytest.raises(InvalidStateError):
        transfer.finish(exception=exception, result=Mock())


async def test_terminate_by_timeout_task(transfer: Transfer):
    transfer.settings.timeout_interval_in_sec = 0

    await transfer.terminate_by_timeout_task()

    assert transfer.finished
    assert transfer.future.done()
    assert isinstance(transfer.future.exception(), TimeoutException)


async def test_terminate_by_timeout_task_disable(transfer: Transfer):
    transfer.settings.terminate_by_timeout_enabled = False

    await transfer.terminate_by_timeout_task()

    assert not transfer.finished
    assert not transfer.future.done()


async def test_terminate_by_timeout_task_finished(transfer: Transfer):
    transfer.settings.timeout_interval_in_sec = 0
    transfer.finished = True

    await transfer.terminate_by_timeout_task()

    assert not transfer.future.done()
