from tribler_common.simpledefs import NTFY

from tribler_core.notifier import Notifier


def test_notifier():
    notifier = Notifier()

    def callback_func(*_):
        callback_func.called = True

    notifier.add_observer(NTFY.TORRENT_FINISHED, callback_func)
    notifier.notify(NTFY.TORRENT_FINISHED)
    assert callback_func.called
