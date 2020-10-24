import asyncio
from unittest.mock import Mock

import pytest

from tribler_common.simpledefs import NTFY

from tribler_core.notifier import Notifier


@pytest.fixture(name="notifier")
def fixture_notifier():
    return Notifier()


@pytest.mark.asyncio
async def test_notifier(notifier):

    mock_foo = Mock()
    notifier.add_observer(NTFY.TORRENT_FINISHED, mock_foo.bar)
    notifier.notify(NTFY.TORRENT_FINISHED)
    # Notifier uses asyncio loop internally, so we must wait at least a single loop cycle
    await asyncio.sleep(0)
    mock_foo.bar.assert_called_once()


def test_remove_observer(notifier):
    def _f():
        pass

    notifier.add_observer(NTFY.TORRENT_FINISHED, _f)
    assert len(notifier.observers) == 1
    assert len(notifier.observers[NTFY.TORRENT_FINISHED]) == 1

    notifier.remove_observer(NTFY.TORRENT_FINISHED, _f)
    assert not notifier.observers[NTFY.TORRENT_FINISHED]

    # raise no error when _f not presents in callbacks
    notifier.remove_observer(NTFY.TORRENT_FINISHED, _f)

    # raise no error when subject not presents in observers
    notifier.remove_observer(NTFY.POPULARITY_COMMUNITY_ADD_UNKNOWN_TORRENT, _f)
