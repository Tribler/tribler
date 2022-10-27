import asyncio
import logging
from unittest.mock import AsyncMock, Mock

import pytest

from tribler.core.components.ipv8.eva.protocol import EVAProtocol, blank
from tribler.core.components.ipv8.eva.settings import EVASettings, Termination
from tribler.core.components.ipv8.eva.transfer.incoming import IncomingTransfer
from tribler.core.components.ipv8.eva.transfer.window import TransferWindow


# pylint: disable=redefined-outer-name, protected-access


@pytest.fixture
async def incoming_transfer():
    settings = EVASettings(
        block_size=10,
        termination=Termination(
            enabled=False
        )
    )
    eva = EVAProtocol(community=Mock(), settings=settings)
    peer = Mock()

    transfer = IncomingTransfer(
        container=eva.incoming,
        info=b'info',
        data_size=100,
        nonce=0,
        protocol_task_group=eva.task_group,
        send_message=Mock(),
        on_complete=blank,
        on_error=blank,
        peer=peer,
        settings=settings
    )

    transfer.container[peer] = transfer

    yield transfer

    await eva.shutdown()


async def test_on_data_normal_packet(incoming_transfer: IncomingTransfer):
    incoming_transfer.window = Mock(is_finished=Mock(return_value=False))
    incoming_transfer.make_acknowledgement = Mock()
    incoming_transfer.update = Mock()
    incoming_transfer.attempt = 2

    incoming_transfer.on_data(3, b'data')

    assert incoming_transfer.window.add.called_with(3, b'data')
    assert incoming_transfer.update.called
    assert incoming_transfer.attempt == incoming_transfer.settings.retransmission.attempts
    assert not incoming_transfer.make_acknowledgement.called


async def test_on_data_window_is_finished(incoming_transfer: IncomingTransfer):
    incoming_transfer.window = Mock(is_finished=Mock(return_value=True))
    incoming_transfer.make_acknowledgement = Mock()
    incoming_transfer.update = Mock()
    incoming_transfer.attempt = 2

    incoming_transfer.on_data(3, b'data')

    assert incoming_transfer.window.add.called_with(3, b'data')
    assert incoming_transfer.update.called
    assert incoming_transfer.attempt == incoming_transfer.settings.retransmission.attempts
    assert incoming_transfer.make_acknowledgement.called
    assert not incoming_transfer.finished


async def test_on_data_window_is_last_and_finished(incoming_transfer: IncomingTransfer):
    incoming_transfer.window = Mock(is_finished=Mock(return_value=True))
    incoming_transfer.make_acknowledgement = Mock()
    incoming_transfer.update = Mock()
    incoming_transfer.finish = AsyncMock()
    incoming_transfer.attempt = 2
    incoming_transfer.last_window = True

    incoming_transfer.on_data(3, b'data')
    await incoming_transfer.protocol_task_group.wait()

    assert incoming_transfer.window.add.called_with(3, b'data')
    assert incoming_transfer.update.called
    assert incoming_transfer.attempt == incoming_transfer.settings.retransmission.attempts
    assert incoming_transfer.make_acknowledgement.called
    assert incoming_transfer.finish.called


async def test_on_data_final_packet(incoming_transfer: IncomingTransfer):
    incoming_transfer.window = TransferWindow(0, 10)
    index = 3

    incoming_transfer.on_data(index, b'')

    assert incoming_transfer.last_window
    assert len(incoming_transfer.window.blocks) == index + 1


async def test_make_acknowledgement_no_window(incoming_transfer: IncomingTransfer):
    assert not incoming_transfer.window

    acknowledgement = incoming_transfer.make_acknowledgement()

    assert incoming_transfer.window
    assert acknowledgement
    assert acknowledgement.number == 0
    assert acknowledgement.window_size == incoming_transfer.settings.window_size


async def test_make_acknowledgement_next_window(incoming_transfer: IncomingTransfer):
    incoming_transfer.window = TransferWindow(10, 7)
    incoming_transfer.window.blocks = [b'd', b'a', b't', b'a', None, None, None]

    acknowledgement = incoming_transfer.make_acknowledgement()

    assert len(incoming_transfer.data_list) == 4
    assert incoming_transfer.window
    assert incoming_transfer.window.start == 4
    assert incoming_transfer.window.processed == 0
    assert len(incoming_transfer.window.blocks) == incoming_transfer.settings.window_size
    assert acknowledgement
    assert acknowledgement.number == 4
    assert acknowledgement.window_size == incoming_transfer.settings.window_size


async def test_finish(incoming_transfer: IncomingTransfer):
    container = incoming_transfer.container
    assert container

    incoming_transfer.finish()

    assert incoming_transfer.data_list is None
    assert not incoming_transfer.container
    assert not container


async def test_send_acknowledge(incoming_transfer: IncomingTransfer):
    incoming_transfer.settings.retransmission.interval = 0

    await incoming_transfer.send_acknowledge()

    assert incoming_transfer.send_message.call_count == 3


async def test_send_acknowledge_finished(incoming_transfer: IncomingTransfer):
    incoming_transfer.settings.retransmission.interval = 0

    def send_message(*_):
        incoming_transfer.finished = True

    incoming_transfer.send_message = Mock(wraps=send_message)

    await incoming_transfer.send_acknowledge()

    assert incoming_transfer.send_message.call_count == 1


async def test_send_acknowledge_updated(incoming_transfer: IncomingTransfer):
    # The timeline for calls:
    #
    # update | __x__x__x________________|
    # send   |x____^__^__^___x____x____x|
    update_sleep_interval = 0.3
    incoming_transfer.settings.retransmission.interval = 0.5
    incoming_transfer._remaining = Mock(wraps=incoming_transfer._remaining)

    async def update_transfer():
        for attempt in range(3):
            logging.debug(f'Sleep({attempt}) {update_sleep_interval}s...')

            await asyncio.sleep(update_sleep_interval)
            # emulate on_data()
            incoming_transfer.update()
            incoming_transfer.attempt = incoming_transfer.settings.retransmission.attempts

    await asyncio.gather(
        update_transfer(),
        incoming_transfer.send_acknowledge()
    )

    assert incoming_transfer.send_message.call_count == 4
    assert incoming_transfer._remaining.call_count == 7
