from Tribler.dispersy.taskmanager import TaskManager
from twisted.internet import reactor
from threading import RLock
import logging


class TwistedRawServer(TaskManager):

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
        reactor.callFromThread(lambda: self.register_task(task_name, reactor.callLater(delay, wrapper)))

    def add_task_in_thread(self, wrapper, delay, task_name=None):
        assert wrapper

        if not task_name:
            with self._lock:
                self._auto_counter += 1
            task_name = "twisted_rawserver %d" % self._auto_counter

        if delay:
            reactor.callFromThread(lambda: reactor.callInThread(wrapper))
        else:
            reactor.callFromThread(lambda: self.register_task(task_name, reactor.callLater(delay, lambda: reactor.callInThread(wrapper))))

    def perform_getstate_usercallback(self, usercallback, data, returncallback):
        def session_getstate_usercallback_target():
            try:
                (when, getpeerlist) = usercallback(data)
                returncallback(usercallback, when, getpeerlist)
            except:
                self._logger.exception('Could not perform usercallback')

        reactor.callFromThread(lambda: reactor.callInThread(session_getstate_usercallback_target))

    def perform_usercallback(self, callback):
        reactor.callFromThread(lambda: reactor.callInThread(callback))

    def queueTask(self, callback, args):
        reactor.callFromThread(lambda: reactor.callInThread(callback, *args))
