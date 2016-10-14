from twisted.internet.defer import Deferred, inlineCallbacks

from Tribler.Core.APIImplementation.threadpoolmanager import ThreadPoolManager
from Tribler.Core.Utilities.twisted_thread import deferred
from Tribler.Test.Core.base_test import TriblerCoreTest
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class TriblerCoreTestThreadpoolManager(TriblerCoreTest):

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self):
        yield super(TriblerCoreTestThreadpoolManager, self).setUp()
        self.tpm = ThreadPoolManager()
        self.callback_deferred = Deferred()

    def callback_func(self):
        self.callback_deferred.callback(None)

    def test_check_task_name(self):
        self.assertEqual(self.tpm._check_task_name("test"), "test")
        self.assertEqual(self.tpm._check_task_name(None), "threadpool_manager 1")

    @deferred(timeout=1)
    def test_add_task(self):
        self.tpm.add_task(self.callback_func, 0.0)
        return self.callback_deferred

    @deferred(timeout=1)
    def test_add_task_in_thread(self):
        self.tpm.add_task_in_thread(self.callback_func, 0.0)
        return self.callback_deferred

    @deferred(timeout=1)
    def test_call(self):
        self.tpm.call(0.0, self.callback_func)
        return self.callback_deferred
