from Tribler.dispersy.taskmanager import TaskManager
from twisted.internet import reactor
from threading import RLock
import logging


class TwistedRawServer(TaskManager):
    _reactor = reactor

    def __init__(self):
        super(TwistedRawServer, self).__init__()
        self._auto_counter = 0
        self._lock = RLock()
        self._logger = logging.getLogger(self.__class__.__name__)

    def add_task(self, wrapper, delay, task_name=None):
        assert wrapper

        if not task_name:
            with self._lock:
                self._auto_counter += 1
            task_name = "twisted_rawserver %d" % self._auto_counter
        reactor.callFromThread(lambda: self.register_task(task_name, self._reactor.callLater(delay, wrapper)))

    def add_task_in_thread(self, wrapper, delay=0, task_name=None):
        assert wrapper

        if not task_name:
            with self._lock:
                self._auto_counter += 1
            task_name = "twisted_rawserver %d" % self._auto_counter

        def delayed_call(delay, task_name):
            self.register_task(task_name, self._reactor.callLater(delay, reactor.callInThread, wrapper))

        reactor.callFromThread(delayed_call, delay, task_name)

    def queueTask(self, callback, args):
        reactor.callFromThread(lambda: reactor.callInThread(callback, *args))
