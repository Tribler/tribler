from unittest.mock import Mock

from tribler.core.components.ipv8.eva.protocol import EVAProtocol
from tribler.core.components.ipv8.eva.transfer import OutgoingTransfer, TransferWindow


def create_transfer() -> OutgoingTransfer:
    block_size = 10
    data_size = 100
    return OutgoingTransfer(info=b'', data=b'd' * data_size, nonce=0, peer=Mock(),
                            protocol=EVAProtocol(Mock(), block_size=block_size))


def test_finished():
    window = TransferWindow(start=0, size=10)
    assert not window.is_finished()

    window.processed = 10
    assert window.is_finished()


def test_block():
    transfer = create_transfer()

    first_block = b'd' * 10
    assert transfer._get_block(0) == first_block

    last_block = transfer._get_block(10)
    assert last_block == b''
