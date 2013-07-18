import unittest
from time import sleep

from Tribler.community.privatesearch.oneswarm.OverlayManager import Average

class TestAverage(unittest.TestCase):
    def setUp(self):
        self.average = Average(1000, 10)

    def tearDown(self):
        del self.average

    def test_add_value(self):
        self.average.addValue(1)
        self.average.addValue(2)

        assert self.average.getSum() == 3, self.average.getSum()

    def test_average(self):
        self.average.addValue(1)
        sleep(1)
        self.average.addValue(2)

        assert self.average.getSum() == 3, self.average.getSum()
        assert self.average.getAverage() == 0.3, self.average.getAverage()

    def test_cleanup(self):
        self.average.addValue(1)
        sleep(11)
        self.average.addValue(2)

        assert self.average.getSum() == 2, self.average.getSum()
        assert self.average.getAverage() == 0.2, self.average.getAverage()

if __name__ == "__main__":
    unittest.main()
