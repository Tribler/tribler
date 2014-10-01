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


class ThreadPool(object):

    """Flexible thread pool class.  Creates a pool of threads, then
    accepts tasks that will be dispatched to the next available
    thread."""

    def __init__(self, num_threads):
        """Initialize the thread pool with num_threads workers."""

        self._logger = logging.getLogger(self.__class__.__name__)

        self.__threads = []
        self.__resizeLock = threading.Condition(threading.Lock())
        self.__taskCond = threading.Condition(threading.Lock())
        self.__tasks = []
        self.__isJoiningStopQueuing = False
        self.__isJoining = False
        self.set_thread_count(num_threads)

    def set_thread_count(self, new_num_threads):
        """ External method to set the current pool size.  Acquires
        the resizing lock, then calls the internal version to do real
        work."""

        # Can't change the thread count if we're shutting down the pool!
        if self.__isJoining:
            return False

        with self.__resizeLock:
            self.__set_thread_count_nolock(new_num_threads)
        return True

    def __set_thread_count_nolock(self, new_num_threads):
        """Set the current pool size, spawning or terminating threads
        if necessary.  Internal use only; assumes the resizing lock is
        held."""

        # If we need to grow the pool, do so
        while new_num_threads > len(self.__threads):
            new_thread = ThreadPoolThread(self)
            self.__threads.append(new_thread)
            new_thread.start()

        # If we need to shrink the pool, do so
        while new_num_threads < len(self.__threads):
            self.__threads[0].go_away()
            del self.__threads[0]

    def get_thread_count(self):
        """Return the number of threads in the pool."""

        with self.__resizeLock:
            return len(self.__threads)

    def queue_task(self, task, args=(), task_callback=None):
        """Insert a task into the queue.  task must be callable;
        args and taskCallback can be None."""

        if self.__isJoining or self.__isJoiningStopQueuing:
            return False
        if not callable(task):
            return False

        with self.__taskCond:
            self.__tasks.append((task, args, task_callback))
            # Arno, 2010-04-07: Use proper notify()+wait()
            self.__taskCond.notifyAll()
            return True

    def get_next_task(self):
        """ Retrieve the next task from the task queue.  For use
        only by ThreadPoolThread objects contained in the pool."""
        self._logger.debug('%d', len(self.__tasks))

        with self.__taskCond:
            while self.__tasks == [] and not self.__isJoining:
                self.__taskCond.wait()
            if self.__isJoining:
                return None, None, None
            else:
                return self.__tasks.pop(0)

    def join_all(self, wait_for_tasks=True, wait_for_threads=True):
        """ Clear the task queue and terminate all pooled threads,
        optionally allowing the tasks and threads to finish."""

        # Mark the pool as joining to prevent any more task queueing
        self.__isJoiningStopQueuing = True

        # Wait for tasks to finish
        if wait_for_tasks:
            while len(self.__tasks) > 0:
                time.sleep(.1)

        # Mark the pool as joining to make all threads stop executing tasks
        self.__isJoining = True

        # Tell all the threads to quit
        with self.__resizeLock:
            current_threads = self.__threads[:]
            self.__set_thread_count_nolock(0)

            # notify all waiting threads that we are quitting
            self.__taskCond.acquire()
            self.__taskCond.notifyAll()
            self.__taskCond.release()

            # Wait until all threads have exited
            if wait_for_threads:
                for t in current_threads:
                    t.join()
                    del t

            # Reset the pool for potential reuse
            self.__isJoining = False


class ThreadNoPool(object):

    def __init__(self):
        self.prevTask = False
        self.__isJoiningStopQueuing = False

        self.queue = Queue()
        self.thread = ThreadPoolThread(self)
        self.thread.start()

    def get_thread_count(self):
        return 1

    def queue_task(self, task, args=(), task_callback=None):
        if not self.__isJoiningStopQueuing:
            self.queue.put((task, args, task_callback))

    def get_next_task(self):
        if self.prevTask:
            self.queue.task_done()
        return self.queue.get()

    def join_all(self, wait_for_tasks=False, wait_for_threads=True):
        self.__isJoiningStopQueuing = True
        self.queue.put((None, (), None))

        if wait_for_tasks:
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
        while not self.__isDying:
            # Arno, 2010-01-28: add try catch block. Sometimes tasks lists grow,
            # could be because all Threads are dying.
            try:
                cmd, args, callback = self.__pool.get_next_task()
                if cmd is None:
                    break
                elif callback is None:
                    cmd(*args)
                else:
                    callback(cmd(args))
            except:
                print_exc()

    def go_away(self):
        """ Exit the run loop next time through."""

        self.__isDying = True
