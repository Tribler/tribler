# Written by Arno Bakker
# see LICENSE.txt for license information
#
# TODO: integrate with test_TimedTaskQueue

import unittest
from time import sleep

from Tribler.Main.Dialogs.GUITaskQueue import GUITaskQueue

DEBUG = False


class TestGUITaskQueue(unittest.TestCase):

    def setUp(self):
        self.ntasks = 0
        self.completed = []
        self.guiserver = GUITaskQueue()

    def tearDown(self):
        sleep(2)
        self.completed.sort()
        if self.completed != range(self.ntasks):
            if DEBUG:
                print "test failed", self.completed
            self.assert_(False)

        self.guiserver.shutdown()
        GUITaskQueue.delInstance()

    def test_simple(self):
        self.ntasks = 1

        self.guiserver.add_task(lambda: self.task(0), 0)

    def test_more(self):
        self.ntasks = 10

        for i in range(self.ntasks):
            # lambda functions are evil, this is not the same as lambda:task(i)
            self.guiserver.add_task(self.define_task(i), 0)

    def test_delay(self):
        self.ntasks = 1

        self.guiserver.add_task(lambda: self.task(0), 3)
        if DEBUG:
            print "test: sleeping 5 secs so tasks get executed"
        sleep(5)

    def test_delay2(self):
        self.ntasks = 2

        self.guiserver.add_task(lambda: self.task(1), 3)
        self.guiserver.add_task(lambda: self.task(0), 1)
        if DEBUG:
            print "test: sleeping 5 secs so tasks get executed"
        sleep(5)

    def define_task(self, num):
        return lambda: self.task(num)

    def task(self, num):
        if DEBUG:
            print "Running task", num
        self.completed.append(num)
