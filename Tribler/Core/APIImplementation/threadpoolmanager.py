
import logging
from os import sys
from threading import RLock

from twisted.internet import reactor
from twisted.internet.defer import Deferred, DeferredList, inlineCallbacks
from twisted.internet.threads import deferToThread

from Tribler.dispersy.taskmanager import TaskManager
from Tribler.dispersy.util import blocking_call_on_reactor_thread


class ThreadPoolManager(TaskManager):
    """
    Enhanced TaskManager that allows you to schedule jobs in the twisted
    threadpool.
    """

    _reactor = reactor

    def __init__(self):
        super(ThreadPoolManager, self).__init__()
        self._auto_counter = 0
        self._lock = RLock()
        self._logger = logging.getLogger(self.__class__.__name__)

    def add_task(self, wrapper, delay=0, task_name=None):
        assert wrapper

        if not task_name:
            with self._lock:
                self._auto_counter += 1
            task_name = "threadpool_manager %d" % self._auto_counter
        reactor.callFromThread(lambda: self.register_task(task_name, self._reactor.callLater(delay, wrapper)))

    def add_task_in_thread(self, wrapper, delay=0, task_name=None):
        assert wrapper

        if not task_name:
            with self._lock:
                self._auto_counter += 1
            task_name = "threadpool_manager %d" % self._auto_counter

        def delayed_call(delay, task_name):
            def call_in_thread():
                self.register_task(task_name + "in_threadpool", deferToThread(wrapper))

            self.register_task(task_name, self._reactor.callLater(delay, call_in_thread))
        reactor.callFromThread(delayed_call, delay, task_name)

    def call(self, delay, fun, *args, **kwargs):
        task_name = kwargs.pop("task_name", None)

        def caller():
            fun(*args, **kwargs)
        self.add_task(caller, delay=delay, task_name=task_name)

    def call_in_thread(self, delay, fun, *args, **kwargs):
        task_name = kwargs.pop("task_name", None)

        def caller():
            fun(*args, **kwargs)
        self.add_task_in_thread(caller, delay=delay, task_name=task_name)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def stop(self):
        dlist = []
        self.cancel_all_pending_tasks()
        for name, task in self._pending_tasks.items():
            if isinstance(task, Deferred):
                print >> sys.stderr, "WAITING FOR DEFERRED:", name
                dlist.append(task)
        d = DeferredList(dlist)
        yield d
