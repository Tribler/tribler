
from Tribler.dispersy.taskmanager import TaskManager
from twisted.internet import reactor
from threading import RLock
import logging


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

    def _check_task_name(self, task_name):
        if not task_name:
            with self._lock:
                self._auto_counter += 1
                task_name = "threadpool_manager %d" % self._auto_counter
        return task_name

    def add_task(self, wrapper, delay=0, task_name=None):
        assert wrapper

        reactor.callFromThread(lambda: self.register_task(self._check_task_name(task_name), self._reactor.callLater(delay, wrapper)))

    def add_task_in_thread(self, wrapper, delay=0, task_name=None):
        assert wrapper

        def delayed_call(delay, task_name):
            self.register_task(self._check_task_name(task_name), self._reactor.callLater(delay, reactor.callInThread, wrapper))

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
