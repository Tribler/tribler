# Written by Arno Bakker
# see LICENSE.txt for license information
#
# TimedTaskQueue is a server that executes tasks on behalf of e.g. the GUI that
# are too time consuming to be run by the actual GUI Thread (MainThread). Note
# that you still need to delegate the actual updating of the GUI to the
# MainThread via the wx.CallAfter mechanism.
#
import logging

from threading import Thread, Condition, RLock, currentThread
from traceback import print_exc, print_stack, format_stack
from time import time
try:
    prctlimported = True
    import prctl
except ImportError as e:
    prctlimported = False


class TimedTaskQueue:

    __single = None

    def __init__(self, nameprefix="TimedTaskQueue", isDaemon=True):
        self._logger = logging.getLogger(self.__class__.__name__)

        self.cond = Condition(RLock())
        self.queue = []
        self.count = 0.0  # serves to keep task that were scheduled at the same time in FIFO order
        self.thread = Thread(target=self.run)
        self.thread.setDaemon(isDaemon)
        self.thread.setName(nameprefix +self.thread.getName())
        self.thread.start()

        if __debug__:
            self.callstack = {}  # callstack by self.count

    def shutdown(self, immediately=False):
        self.add_task("stop", -time() if immediately else 0)
        self.add_task = lambda task, t=0, id=None: None

    def add_task(self, task, t=0, id=None):
        """ t parameter is now usable, unlike before.
            If id is given, all the existing tasks with the same id will be removed
            before inserting this task
        """

        if task is None:
            print_stack()

        self.cond.acquire()
        when = time() + t

        debug_call_name = task.__name__ if hasattr(task, "__name__") else str(task)
        self._logger.debug("ttqueue: ADD EVENT %s %s %s", t, task, debug_call_name)

        if __debug__:
            self.callstack[self.count] = format_stack()

        if id != None:  # remove all redundant tasks
            self.queue = filter(lambda item: item[3] != id, self.queue)
        self.queue.append((when, self.count, task, id))
        self.count += 1.0
        self.cond.notify()
        self.cond.release()

    def remove_task(self, id):
        self.cond.acquire()
        self.queue = filter(lambda item: item[3] != id, self.queue)
        self.cond.notify()
        self.cond.release()

    def does_task_exist(self, id):
        return any(item[3] == id for item in self.queue)

    def get_nr_tasks(self):
        return len(self.queue)

    def run(self):
        """ Run by server thread """

        if prctlimported:
            prctl.set_name("Tribler" + currentThread().getName())

        while True:
            task = None
            timeout = None
            flag = False
            self.cond.acquire()
            while True:
                while len(self.queue) == 0 or flag:
                    flag = False
                    if timeout is None:
                        # Wait until something is queued
                        self.cond.wait()
                    else:
                        # Wait till first event is due
                        self.cond.wait(timeout)
                # A new event was added or an event is due
                self.queue.sort()

                (when, count, task, id) = self.queue[0]
                self._logger.debug("ttqueue: EVENT IN QUEUE %s %s", when, task)
                now = time()
                if now < when:
                    # Event not due, wait some more
                    self._logger.debug("ttqueue: EVENT NOT TILL %s", when - now)
                    timeout = when - now
                    flag = True
                else:
                    # Event due, execute
                    self._logger.debug("ttqueue: EVENT DUE")
                    self.queue.pop(0)
                    if __debug__:
                        assert count in self.callstack
                        stack = self.callstack.pop(count)
                    break
            self.cond.release()

            # Execute task outside lock
            try:
                # 'stop' and 'quit' are only used for unit test
                if task == 'stop':
                    break
                elif task == 'quit':
                    if len(self.queue) == 0:
                        break
                    else:
                        (when, count, task, id) = self.queue[-1]
                        t = when - time() +0.001
                        self.add_task('quit', t)
                else:
                    t1 = time()

                    task()

                    took = time() - t1
                    if took > 0.2:
                        debug_call_name = task.__name__ if hasattr(task, "__name__") else str(task)
                        self._logger.debug("ttqueue: EVENT TOOK %s %s", took, debug_call_name)
            except:
                print_exc()
                if __debug__:
                    self._logger.debug("<<<<<<<<<<<<<<<<")
                    self._logger.debug("TASK QUEUED FROM")
                    self._logger.debug("".join(stack))
                    self._logger.debug(">>>>>>>>>>>>>>>>")
