# Written by Arno Bakker
# see LICENSE.txt for license information

import unittest

import sys
import time
from traceback import print_exc
from threading import RLock, enumerate as enumerate_threads

from Tribler.Core.APIImplementation.ThreadPool import ThreadPool


DEBUG = False


class TestThreadPool(unittest.TestCase):

    """
    Parent class for testing internal thread pool of Tribler
    """

    def setUp(self):
        """ unittest test setup code """
        self.tp = ThreadPool(10)
        self.exp = []
        self.gotlock = RLock()
        self.got = []

    def tearDown(self):
        """ unittest test tear down code """
        self.tp.joinAll()

        time.sleep(2)
        self.got.sort()
        self.assertEquals(self.exp, self.got)

        ts = enumerate_threads()
        print >> sys.stderr, "test_threadpool: Number of threads still running", len(ts)
        for t in ts:
            print >> sys.stderr, "test_threadpool: Thread still running", t.getName(), "daemon", t.isDaemon(), "instance:", t

    def test_queueTask1(self):
        if DEBUG:
            print >> sys.stderr, "test_queueTask1:"
        self.exp = [1]
        self.tp.queueTask(lambda: self.do_task(1))

    def do_task(self, val):
        self.gotlock.acquire()
        if DEBUG:
            print >> sys.stderr, "test: got task", val
        self.got.append(val)
        self.gotlock.release()

    def test_queueTask10lambda(self):
        if DEBUG:
            print >> sys.stderr, "test_queueTask10lambda:"
        self.exp = range(1, 11)

        def wrapper(x):
            self.tp.queueTask(lambda: self.do_task(x))

        for i in range(1, 11):
            if DEBUG:
                print >> sys.stderr, "test: exp task", i
            wrapper(i)

    #
    # Confusing lambda crap, do explicit:
    #
    def test_queueTask10explicit(self):
        if DEBUG:
            print >> sys.stderr, "test_queueTask10explicit:"
        self.exp = range(1, 11)
        self.tp.queueTask(self.do_task1)
        self.tp.queueTask(self.do_task2)
        self.tp.queueTask(self.do_task3)
        self.tp.queueTask(self.do_task4)
        self.tp.queueTask(self.do_task5)
        self.tp.queueTask(self.do_task6)
        self.tp.queueTask(self.do_task7)
        self.tp.queueTask(self.do_task8)
        self.tp.queueTask(self.do_task9)
        self.tp.queueTask(self.do_task10)

    def test_joinAll(self):
        if DEBUG:
            print >> sys.stderr, "test_joinall:"
        self.exp = range(1, 6)
        if DEBUG:
            print >> sys.stderr, "test: adding tasks"
        self.tp.queueTask(self.do_task1)
        self.tp.queueTask(self.do_task2)
        self.tp.queueTask(self.do_task3)
        self.tp.queueTask(self.do_task4)
        self.tp.queueTask(self.do_task5)
        if DEBUG:
            print >> sys.stderr, "test: join all"
        self.tp.joinAll()
        if DEBUG:
            print >> sys.stderr, "test: adding post tasks, shouldn't get run"
        self.tp.queueTask(self.do_task6)
        self.tp.queueTask(self.do_task7)
        self.tp.queueTask(self.do_task8)
        self.tp.queueTask(self.do_task9)
        self.tp.queueTask(self.do_task10)

    def test_setThreadCountPlus10(self):
        if DEBUG:
            print >> sys.stderr, "test_setThreadCountPlus10:"
            print >> sys.stderr, "test: pre threads", self.tp.getThreadCount()
        self.tp.setThreadCount(20)
        if DEBUG:
            print >> sys.stderr, "test: post threads", self.tp.getThreadCount()
        time.sleep(1)
        self.test_joinAll()

    def test_setThreadCountMinus8(self):
        if DEBUG:
            print >> sys.stderr, "test_setThreadCountMinus8:"
            print >> sys.stderr, "test: pre threads", self.tp.getThreadCount()
        self.tp.setThreadCount(2)
        if DEBUG:
            print >> sys.stderr, "test: post threads", self.tp.getThreadCount()
        time.sleep(1)
        self.test_joinAll()

    def do_task1(self):
        self.gotlock.acquire()
        self.got.append(1)
        self.gotlock.release()

    def do_task2(self):
        self.gotlock.acquire()
        self.got.append(2)
        self.gotlock.release()

    def do_task3(self):
        self.gotlock.acquire()
        self.got.append(3)
        self.gotlock.release()

    def do_task4(self):
        self.gotlock.acquire()
        self.got.append(4)
        self.gotlock.release()

    def do_task5(self):
        self.gotlock.acquire()
        self.got.append(5)
        self.gotlock.release()

    def do_task6(self):
        self.gotlock.acquire()
        self.got.append(6)
        self.gotlock.release()

    def do_task7(self):
        self.gotlock.acquire()
        self.got.append(7)
        self.gotlock.release()

    def do_task8(self):
        self.gotlock.acquire()
        self.got.append(8)
        self.gotlock.release()

    def do_task9(self):
        self.gotlock.acquire()
        self.got.append(9)
        self.gotlock.release()

    def do_task10(self):
        self.gotlock.acquire()
        self.got.append(10)
        self.gotlock.release()
