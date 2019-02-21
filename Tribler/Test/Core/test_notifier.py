from __future__ import absolute_import

from twisted.internet.defer import Deferred, inlineCallbacks

from Tribler.Core.Notifier import Notifier
from Tribler.Core.simpledefs import NTFY_FINISHED, NTFY_STARTED, NTFY_TORRENTS
from Tribler.Test.Core.base_test import TriblerCoreTest
from Tribler.Test.tools import trial_timeout


class TriblerCoreTestNotifier(TriblerCoreTest):

    @inlineCallbacks
    def setUp(self):
        yield super(TriblerCoreTestNotifier, self).setUp()
        self.test_deferred = Deferred()
        self.called_callback = False

    def callback_func(self, subject, changetype, objectID, *args):
        self.called_callback = True
        self.test_deferred.callback(None)

    def cache_callback_func(self, events):
        self.called_callback = True
        self.test_deferred.callback(None)

    @trial_timeout(10)
    def test_notifier(self):
        notifier = Notifier()
        notifier.add_observer(self.callback_func, NTFY_TORRENTS, [NTFY_STARTED])
        notifier.notify(NTFY_TORRENTS, NTFY_STARTED, None)
        notifier.remove_observer(self.callback_func)
        return self.test_deferred

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

    @trial_timeout(10)
    def test_notifier_cache(self):
        notifier = Notifier()
        notifier.add_observer(self.cache_callback_func, NTFY_TORRENTS, [NTFY_STARTED], cache=0.1)
        notifier.notify(NTFY_TORRENTS, NTFY_STARTED, None)
        return self.test_deferred

    @trial_timeout(10)
    def test_notifier_cache_notify_twice(self):
        notifier = Notifier()
        notifier.add_observer(self.cache_callback_func, NTFY_TORRENTS, [NTFY_STARTED], cache=0.1)
        notifier.notify(NTFY_TORRENTS, NTFY_STARTED, None)
        notifier.notify(NTFY_TORRENTS, NTFY_STARTED, None)
        return self.test_deferred

    def test_notifier_cache_remove_observers(self):
        notifier = Notifier()
        notifier.add_observer(self.cache_callback_func, NTFY_TORRENTS, [NTFY_STARTED], cache=10)
        notifier.notify(NTFY_TORRENTS, NTFY_STARTED, None)
        notifier.remove_observers()
        self.assertEqual(len(notifier.observertimers), 0)
