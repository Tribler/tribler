import datetime
import unittest

from Tribler.community.chant.timeutils import time2float, float2time, EPOCH


class TestTimeutils(unittest.TestCase):

    def setUp(self):
        self.test_time_list = [
            datetime.datetime(2005, 7, 14, 12, 30, 12, 1234),
            datetime.datetime(2039, 7, 14, 12, 30, 12, 1234),
            datetime.datetime.utcnow()]

    def test_time_convert(self):
        for tm in self.test_time_list:
            self.assertTrue(tm == float2time(time2float(tm)))

    def test_zero_time(self):
        self.assertTrue(float2time(0.0) == EPOCH)

    def test_negative_time(self):
        negtm = EPOCH - datetime.timedelta(1)
        self.assertTrue(negtm == float2time(time2float(negtm)))
