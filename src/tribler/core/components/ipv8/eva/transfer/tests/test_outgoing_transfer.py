from unittest.mock import AsyncMock, Mock

import pytest

from tribler.core.components.ipv8.eva.exceptions import SizeException
from tribler.core.components.ipv8.eva.protocol import Data, EVAProtocol, TransferResult
from tribler.core.components.ipv8.eva.transfer.outgoing_transfer import OutgoingTransfer


@pytest.fixture
def outgoing_transfer() -> OutgoingTransfer:
    return OutgoingTransfer(info=b'info', data=b'binary_data', nonce=0, on_complete=AsyncMock(), peer=Mock(),
                            protocol=EVAProtocol(Mock(), block_size=2))


def test_size_exception():
    eva = EVAProtocol(Mock(), block_size=10)
    limit = eva.binary_size_limit
    with pytest.raises(SizeException):
        OutgoingTransfer(info=b'info', data=b'd' * (limit + 1), nonce=0, on_complete=AsyncMock(), peer=Mock(),
                         protocol=eva)


def test_block_count(outgoing_transfer: OutgoingTransfer):
    # data is b'binary_data' and block_size is `2`
    assert outgoing_transfer.block_count == 6


def test_on_acknowledgement(outgoing_transfer: OutgoingTransfer):
    assert not outgoing_transfer.acknowledgement_received
    assert not outgoing_transfer.updated

    actual = list(outgoing_transfer.on_acknowledgement(ack_number=0, window_size=16))

    assert outgoing_transfer.acknowledgement_received
    assert outgoing_transfer.updated
    expected = [
        Data(0, 0, b'bi'),
        Data(1, 0, b'na'),
        Data(2, 0, b'ry'),
        Data(3, 0, b'_d'),
        Data(4, 0, b'at'),
        Data(5, 0, b'a'),
        Data(6, 0, b''),
    ]

    assert all(a.data == e.data and a.number == e.number for a, e in zip(actual, expected))


def test_on_final_acknowledgement(outgoing_transfer: OutgoingTransfer):
    outgoing_transfer.finish = Mock()
    data_list = list(outgoing_transfer.on_acknowledgement(ack_number=10, window_size=16))
    expected_result = TransferResult(peer=outgoing_transfer.peer, info=outgoing_transfer.info,
                                     data=outgoing_transfer.data, nonce=outgoing_transfer.nonce)
    assert not data_list
    assert outgoing_transfer.finish.called_with(result=expected_result)


async def test_finish(outgoing_transfer: OutgoingTransfer):
    eva = outgoing_transfer.protocol
    eva.outgoing[outgoing_transfer.peer] = outgoing_transfer

    outgoing_transfer.finish()

    assert not eva.outgoing
    assert not outgoing_transfer.data


def test_get_block(outgoing_transfer: OutgoingTransfer):
    assert outgoing_transfer._get_block(0) == b'bi'
    assert outgoing_transfer._get_block(1) == b'na'
    ...
    assert outgoing_transfer._get_block(5) == b'a'
    assert outgoing_transfer._get_block(6) == b''
