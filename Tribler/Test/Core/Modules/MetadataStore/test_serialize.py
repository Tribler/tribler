import datetime

from Tribler.Core.Modules.MetadataStore.serialization import float2time, time2float, EPOCH
from Tribler.Test.Core.base_test import TriblerCoreTest


class TestTimeUtils(TriblerCoreTest):

    def test_time_convert(self):
        """
        Test converting various datetime objects to float
        """
        test_time_list = [
            datetime.datetime(2005, 7, 14, 12, 30, 12, 1234),
            datetime.datetime(2039, 7, 14, 12, 30, 12, 1234),
            datetime.datetime.utcnow()
        ]
        for test_time in test_time_list:
            self.assertTrue(test_time == float2time(time2float(test_time)))

    def test_zero_time(self):
        """
        Test whether a time of zero converts to the epoch time
        """
        self.assertTrue(float2time(0.0) == EPOCH)

    def test_negative_time(self):
        """
        Test whether we are able to deal with time below the epoch time
        """
        negative_time = EPOCH - datetime.timedelta(1)
        self.assertTrue(negative_time == float2time(time2float(negative_time)))
