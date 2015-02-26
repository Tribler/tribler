from time import sleep

from Tribler.Test.test_as_server import BaseTestCase
from Tribler.Utilities.TimedTaskQueue import TimedTaskQueue


class TestTimedTaskQueue(BaseTestCase):

    def setUp(self):
        self.queue = TimedTaskQueue()

    def tearDown(self):
        self.queue.shutdown()
        del self.queue

    def test_addTask(self):
        self.count = 0
        self.queue.add_task(self.task3a, 3)
        self.queue.add_task(self.task0, 0)
        self.queue.add_task(self.task3b, 3)
        self.queue.add_task(self.task2, 1)
        sleep(6)
        assert self.count == 11

    def task0(self):
        self.count += 1
        assert self.count == 1

    def task2(self):
        self.count += 2
        assert self.count == 3

    def task3a(self):
        self.count += 4
        assert self.count == 7 or self.count == 11

    def task3b(self):
        self.count += 4
        assert self.count == 7 or self.count == 11

    def test_addTask0FIFO(self):
        self.count = 0
        self.queue.add_task(self.task0a, 0)
        self.queue.add_task(self.task0b, 0)
        self.queue.add_task(self.task0c, 0)
        self.queue.add_task(self.task0d, 0)
        sleep(6)
        assert self.count == 4

    def task0a(self):
        assert self.count == 0
        self.count = 1

    def task0b(self):
        assert self.count == 1
        self.count = 2

    def task0c(self):
        assert self.count == 2
        self.count = 3

    def task0d(self):
        assert self.count == 3
        self.count = 4
