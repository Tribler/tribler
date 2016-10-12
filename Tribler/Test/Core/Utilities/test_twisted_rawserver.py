# Written by Arno Bakker
# see LICENSE.txt for license information
import sys
import time
from threading import RLock, enumerate as enumerate_threads

from twisted.internet.defer import Deferred
from twisted.internet.task import Clock

from Tribler.Core.APIImplementation.threadpoolmanager import ThreadPoolManager
from Tribler.Core.Utilities.twisted_thread import deferred, reactor
from Tribler.Test.test_as_server import AbstractServer


class TestThreadPoolManager(AbstractServer):

    """
    Test ThreadPoolManager thread pool and task scheduler
    """

    def setUp(self):
        AbstractServer.setUp(self)
        self.threadpool = ThreadPoolManager()
        self.clock = self.threadpool._reactor = Clock()
        self.exp = []
        self.gotlock = RLock()
        self.got = []

    def tearDown(self):
        self.threadpool.cancel_all_pending_tasks()
        self.clock.advance(len(self.exp))
        self.got.sort()
        self.assertEquals(self.exp, self.got)

        super(TestThreadPoolManager, self).tearDown()

    def do_task(self, val):
        self.gotlock.acquire()
        self.got.append(val)
        self.gotlock.release()

    @deferred(timeout=1)
    def test_task_scheduling_in_reactor(self):
        """
        Schedule 10 calls in 1 second intervals on the reactor, 11 seconds later all
        of them are called in the correct order.
        """
        self.exp = range(11)
        d = Deferred()
        self.threadpool.add_task(lambda: self.do_task(0), 0)
        self.threadpool.add_task(lambda: self.do_task(1), 1)
        self.threadpool.add_task(lambda: self.do_task(2), 2)
        self.threadpool.add_task(lambda: self.do_task(3), 3)
        self.threadpool.add_task(lambda: self.do_task(4), 4)
        self.threadpool.add_task(lambda: self.do_task(5), 5)
        self.threadpool.add_task(lambda: self.do_task(6), 6)
        self.threadpool.add_task(lambda: self.do_task(7), 7)
        self.threadpool.add_task(lambda: self.do_task(8), 8)
        self.threadpool.add_task(lambda: self.do_task(9), 9)
        self.threadpool.add_task(lambda: self.do_task(10), 10)

        self.threadpool.add_task(lambda: d.callback(None), 11)

        reactor.callFromThread(self.clock.advance, 11)
        return d

    @deferred(timeout=1)
    def test_task_scheduling_in_reactor_concurrent(self):
        """
        Schedule 10 calls on the reactor to be called at the same point in time, 1
        second later all of them are called in the order they have been
        scheduled.
        """
        self.exp = range(11)
        d = Deferred()
        self.threadpool.add_task(lambda: self.do_task(0), 0)
        self.threadpool.add_task(lambda: self.do_task(1), 0)
        self.threadpool.add_task(lambda: self.do_task(2), 0)
        self.threadpool.add_task(lambda: self.do_task(3), 0)
        self.threadpool.add_task(lambda: self.do_task(4), 0)
        self.threadpool.add_task(lambda: self.do_task(5), 0)
        self.threadpool.add_task(lambda: self.do_task(6), 0)
        self.threadpool.add_task(lambda: self.do_task(7), 0)
        self.threadpool.add_task(lambda: self.do_task(8), 0)
        self.threadpool.add_task(lambda: self.do_task(9), 0)
        self.threadpool.add_task(lambda: self.do_task(10), 0)

        self.threadpool.add_task(lambda: d.callback(None), 1)

        reactor.callFromThread(self.clock.advance, 1)
        return d

    @deferred(timeout=1)
    def test_task_scheduling_in_reactor_partial(self):
        """
        Schedule 10 calls in 1 second intervals on the reactor, 5 seconds later only
        the first 5 have been called.
        """
        self.exp = range(5)
        d = Deferred()
        self.threadpool.add_task(lambda: self.do_task(0), 0)
        self.threadpool.add_task(lambda: self.do_task(1), 1)
        self.threadpool.add_task(lambda: self.do_task(2), 2)
        self.threadpool.add_task(lambda: self.do_task(3), 3)
        self.threadpool.add_task(lambda: self.do_task(4), 4)

        self.threadpool.add_task(lambda: d.callback(None), 5)

        self.threadpool.add_task(lambda: self.do_task(6), 6)
        self.threadpool.add_task(lambda: self.do_task(7), 7)
        self.threadpool.add_task(lambda: self.do_task(8), 8)
        self.threadpool.add_task(lambda: self.do_task(9), 9)
        self.threadpool.add_task(lambda: self.do_task(10), 10)

        reactor.callFromThread(self.clock.advance, 5)
        return d

    @deferred(timeout=1)
    def test_task_scheduling_in_thread_pool(self):
        """
        Schedule 10 calls in 1 second intervals on the threadpool, 11 seconds later
        all of them are called in the correct order.
        """
        self.exp = range(11)
        d = Deferred()
        self.threadpool.add_task_in_thread(lambda: self.do_task(0), 0)
        self.threadpool.add_task_in_thread(lambda: self.do_task(1), 1)
        self.threadpool.add_task_in_thread(lambda: self.do_task(2), 2)
        self.threadpool.add_task_in_thread(lambda: self.do_task(3), 3)
        self.threadpool.add_task_in_thread(lambda: self.do_task(4), 4)
        self.threadpool.add_task_in_thread(lambda: self.do_task(5), 5)
        self.threadpool.add_task_in_thread(lambda: self.do_task(6), 6)
        self.threadpool.add_task_in_thread(lambda: self.do_task(7), 7)
        self.threadpool.add_task_in_thread(lambda: self.do_task(8), 8)
        self.threadpool.add_task_in_thread(lambda: self.do_task(9), 9)
        self.threadpool.add_task_in_thread(lambda: self.do_task(10), 10)

        self.threadpool.add_task_in_thread(lambda: d.callback(None), 11)

        reactor.callFromThread(self.clock.advance, 11)
        return d

    @deferred(timeout=1)
    def test_task_scheduling_in_thread_pool_partial(self):
        """
        Schedule 10 calls in 1 second intervals on the threadpool, 5 seconds later
        only the first 5 have been called.
        """
        self.exp = range(5)
        d = Deferred()
        self.threadpool.add_task_in_thread(lambda: self.do_task(0), 0)
        self.threadpool.add_task_in_thread(lambda: self.do_task(1), 1)
        self.threadpool.add_task_in_thread(lambda: self.do_task(2), 2)
        self.threadpool.add_task_in_thread(lambda: self.do_task(3), 3)
        self.threadpool.add_task_in_thread(lambda: self.do_task(4), 4)

        self.threadpool.add_task_in_thread(lambda: d.callback(None), 5)

        self.threadpool.add_task_in_thread(lambda: self.do_task(6), 6)
        self.threadpool.add_task_in_thread(lambda: self.do_task(7), 7)
        self.threadpool.add_task_in_thread(lambda: self.do_task(8), 8)
        self.threadpool.add_task_in_thread(lambda: self.do_task(9), 9)
        self.threadpool.add_task_in_thread(lambda: self.do_task(10), 10)

        reactor.callFromThread(self.clock.advance, 5)
        return d
