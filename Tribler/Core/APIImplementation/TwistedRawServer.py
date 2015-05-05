from Tribler.dispersy.taskmanager import TaskManager
from twisted.internet import reactor
from threading import RLock

class TwistedRawServer(TaskManager):

    def __init__(self):
        super(TwistedRawServer, self).__init__()
        self._auto_counter = 0
        self._lock = RLock()

    def add_task(self, wrapper, delay):
        with self._lock:
            self._auto_counter += 1

        task_name = "twisted_rawserver %d" % self._auto_counter
        reactor.callFromThread(lambda: self.register_task(task_name, reactor.callLater(delay, wrapper)))