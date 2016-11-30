import time
from Tribler.Core.CacheDB.Notifier import Notifier
from Tribler.Core.simpledefs import NTFY_TORRENTS, NTFY_STARTED, NTFY_FINISHED
from Tribler.Test.Core.base_test import TriblerCoreTest


class TriblerCoreTestNotifier(TriblerCoreTest):

    called_callback = False

    def callback_func(self, subject, changetype, objectID, *args):
        self.called_callback = True

    def cache_callback_func(self, events):
        self.called_callback = True

    def wait_for_callback(self):
        counter = 0
        while not self.called_callback:
            if counter == 100:
                raise RuntimeError('Callback not called')
            time.sleep(0.01)
            counter += 1

    def test_notifier_no_threadpool(self):
        notifier = Notifier()
        notifier.add_observer(self.callback_func, NTFY_TORRENTS, [NTFY_STARTED])
        notifier.notify(NTFY_TORRENTS, NTFY_STARTED, None)
        self.wait_for_callback()
        notifier.remove_observer(self.called_callback)

    def test_notifier_threadpool(self):
        notifier = Notifier()
        notifier.add_observer(self.callback_func, NTFY_TORRENTS, [NTFY_STARTED])
        notifier.notify(NTFY_TORRENTS, NTFY_STARTED, None)
        self.wait_for_callback()

    def test_notifier_remove_observers(self):
        notifier = Notifier()
        notifier.add_observer(self.callback_func, NTFY_TORRENTS, [NTFY_STARTED])
        notifier.remove_observers()
        self.assertTrue(len(notifier.observers) == 0)

    def test_notifier_no_observers(self):
        notifier = Notifier()
        notifier.notify(NTFY_TORRENTS, NTFY_STARTED, None)
        self.assertFalse(self.called_callback)

    def test_notifier_wrong_changetype(self):
        notifier = Notifier()
        notifier.add_observer(self.callback_func, NTFY_TORRENTS, [NTFY_STARTED])
        notifier.notify(NTFY_TORRENTS, NTFY_FINISHED, None)
        self.assertFalse(self.called_callback)

    def test_notifier_cache(self):
        notifier = Notifier()
        notifier.add_observer(self.cache_callback_func, NTFY_TORRENTS, [NTFY_STARTED], cache=0.1)
        notifier.notify(NTFY_TORRENTS, NTFY_STARTED, None)
        self.wait_for_callback()

    def test_notifier_cache_notify_twice(self):
        notifier = Notifier()
        notifier.add_observer(self.cache_callback_func, NTFY_TORRENTS, [NTFY_STARTED], cache=0.1)
        notifier.notify(NTFY_TORRENTS, NTFY_STARTED, None)
        notifier.notify(NTFY_TORRENTS, NTFY_STARTED, None)
        self.wait_for_callback()

    def test_notifier_cache_remove_observers(self):
        notifier = Notifier()
        notifier.add_observer(self.cache_callback_func, NTFY_TORRENTS, [NTFY_STARTED], cache=10)
        notifier.notify(NTFY_TORRENTS, NTFY_STARTED, None)
        notifier.remove_observers()
        self.assertEqual(len(notifier.observertimers), 0)
