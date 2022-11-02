import pytest

from tribler.core.components.ipv8.eva.transfer.window import TransferWindow


# pylint: disable=redefined-outer-name

@pytest.fixture
async def window() -> TransferWindow:
    return TransferWindow(start=0, size=10)


def test_constructor(window: TransferWindow):
    assert len(window.blocks) == 10
    assert all(not block for block in window.blocks)


def test_add(window: TransferWindow):
    window.add(0, b'first')
    window.add(0, b'first')
    window.add(9, b'last')

    assert window.blocks == [b'first', None, None, None, None, None, None, None, None, b'last']
    assert window.processed == 2
    assert not window.is_finished()


def test_finished(window: TransferWindow):
    for i in range(10):
        window.add(i, b'block')

    assert window.processed == 10
    assert window.is_finished()


def test_consecutive_blocks(window: TransferWindow):
    window.add(0, b'first')
    window.add(1, b'second')
    window.add(3, b'fourth')

    actual = list(window.consecutive_blocks())

    assert actual == [b'first', b'second']
