import pytest

from tribler_common.simpledefs import NTFY

from tribler_core.notifier import Notifier


@pytest.fixture(name="notifier")
def fixture_notifier():
    return Notifier()


def test_notifier(notifier):
    def callback_func(*_):
        callback_func.called = True

    notifier.add_observer(NTFY.TORRENT_FINISHED, callback_func)
    notifier.notify(NTFY.TORRENT_FINISHED)
    assert callback_func.called


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
