# Written by Jelle Roozenburg, Arno Bakker
# see LICENSE.txt for license information

import time
from traceback import print_exc
import threading
import logging
from Queue import Queue
try:
    prctlimported = True
    import prctl
except ImportError as e:
    prctlimported = False


class ThreadPool:

    """Flexible thread pool class.  Creates a pool of threads, then
    accepts tasks that will be dispatched to the next available
    thread."""

    def __init__(self, numThreads):
        """Initialize the thread pool with numThreads workers."""

        self._logger = logging.getLogger(self.__class__.__name__)

        self.__threads = []
        self.__resizeLock = threading.Condition(threading.Lock())
        self.__taskCond = threading.Condition(threading.Lock())
        self.__tasks = []
        self.__isJoiningStopQueuing = False
        self.__isJoining = False
        self.setThreadCount(numThreads)

    def setThreadCount(self, newNumThreads):
        """ External method to set the current pool size.  Acquires
        the resizing lock, then calls the internal version to do real
        work."""

        # Can't change the thread count if we're shutting down the pool!
        if self.__isJoining:
            return False

        self.__resizeLock.acquire()
        try:
            self.__setThreadCountNolock(newNumThreads)
        finally:
            self.__resizeLock.release()
        return True

    def __setThreadCountNolock(self, newNumThreads):
        """Set the current pool size, spawning or terminating threads
        if necessary.  Internal use only; assumes the resizing lock is
        held."""

        # If we need to grow the pool, do so
        while newNumThreads > len(self.__threads):
            newThread = ThreadPoolThread(self)
            self.__threads.append(newThread)
            newThread.start()

        # If we need to shrink the pool, do so
        while newNumThreads < len(self.__threads):
            self.__threads[0].goAway()
            del self.__threads[0]

    def getThreadCount(self):
        """Return the number of threads in the pool."""

        self.__resizeLock.acquire()
        try:
            return len(self.__threads)
        finally:
            self.__resizeLock.release()

    def queueTask(self, task, args=(), taskCallback=None):
        """Insert a task into the queue.  task must be callable;
        args and taskCallback can be None."""

        if self.__isJoining == True or self.__isJoiningStopQueuing:
            return False
        if not callable(task):
            return False

        self.__taskCond.acquire()
        try:
            self.__tasks.append((task, args, taskCallback))
            # Arno, 2010-04-07: Use proper notify()+wait()
            self.__taskCond.notifyAll()
            return True
        finally:
            self.__taskCond.release()

    def getNextTask(self):
        """ Retrieve the next task from the task queue.  For use
        only by ThreadPoolThread objects contained in the pool."""
        self._logger.debug('%d', len(self.__tasks))

        self.__taskCond.acquire()
        try:
            while self.__tasks == [] and not self.__isJoining:
                self.__taskCond.wait()
            if self.__isJoining:
                return (None, None, None)
            else:
                return self.__tasks.pop(0)
        finally:
            self.__taskCond.release()

    def joinAll(self, waitForTasks=True, waitForThreads=True):
        """ Clear the task queue and terminate all pooled threads,
        optionally allowing the tasks and threads to finish."""

        # Mark the pool as joining to prevent any more task queueing
        self.__isJoiningStopQueuing = True

        # Wait for tasks to finish
        if waitForTasks:
            while self.__tasks != []:
                time.sleep(.1)

        # Mark the pool as joining to make all threads stop executing tasks
        self.__isJoining = True

        # Tell all the threads to quit
        self.__resizeLock.acquire()
        try:
            currentThreads = self.__threads[:]
            self.__setThreadCountNolock(0)

            # notify all waiting threads that we are quitting
            self.__taskCond.acquire()
            self.__taskCond.notifyAll()
            self.__taskCond.release()

            # Wait until all threads have exited
            if waitForThreads:
                for t in currentThreads:
                    t.join()
                    del t

            # Reset the pool for potential reuse
            self.__isJoining = False
        finally:
            self.__resizeLock.release()


class ThreadNoPool:

    def __init__(self):
        self.prevTask = False
        self.__isJoiningStopQueuing = False

        self.queue = Queue()
        self.thread = ThreadPoolThread(self)
        self.thread.start()

    def getThreadCount(self):
        return 1

    def queueTask(self, task, args=(), taskCallback=None):
        if not self.__isJoiningStopQueuing:
            self.queue.put((task, args, taskCallback))

    def getNextTask(self):
        if self.prevTask:
            self.queue.task_done()
        return self.queue.get()

    def joinAll(self, waitForTasks=False, waitForThreads=True):
        self.__isJoiningStopQueuing = True
        self.queue.put((None, (), None))

        if waitForTasks:
            self.thread.join()


class ThreadPoolThread(threading.Thread):

    """ Pooled thread class. """

    def __init__(self, pool):
        """ Initialize the thread and remember the pool. """

        threading.Thread.__init__(self)
        self.setName('SessionPool' + self.getName())
        self.setDaemon(True)
        self.__pool = pool
        self.__isDying = False

    def run(self):
        """ Until told to quit, retrieve the next task and execute
        it, calling the callback if any.  """

        if prctlimported:
            prctl.set_name("Tribler" + threading.currentThread().getName())

        # Arno, 2010-04-07: Dying only used when shrinking pool now.
        while self.__isDying == False:
            # Arno, 2010-01-28: add try catch block. Sometimes tasks lists grow,
            # could be because all Threads are dying.
            try:
                cmd, args, callback = self.__pool.getNextTask()
                if cmd is None:
                    break
                elif callback is None:
                    cmd(*args)
                else:
                    callback(cmd(args))
            except:
                print_exc()

    def goAway(self):
        """ Exit the run loop next time through."""

        self.__isDying = True
