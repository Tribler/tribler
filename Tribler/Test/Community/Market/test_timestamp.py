import time
import unittest

from Tribler.community.market.core.timestamp import Timestamp


class TimestampTestSuite(unittest.TestCase):
    """Timestamp test cases."""

    def test_timestamp(self):
        # Object creation
        timestamp = Timestamp(1462224447.117)
        timestamp2 = Timestamp(1462224447.117)
        timestamp3 = Timestamp(1305743832.438)

        # Test for init validation
        with self.assertRaises(ValueError):
            Timestamp(-1.0)

        # Test for now
        self.assertEqual(time.time(), float(Timestamp.now()))

        # Test for conversions
        self.assertEqual(1462224447.117, float(timestamp))
        self.assertEqual('2016-05-02 23:27:27.117000', str(timestamp))

        # Test for comparison
        self.assertTrue(timestamp3 < timestamp)
        self.assertTrue(timestamp <= timestamp)
        self.assertTrue(timestamp > timestamp3)
        self.assertTrue(timestamp3 >= timestamp3)
        self.assertTrue(timestamp3 < 1405743832.438)
        self.assertTrue(timestamp <= 1462224447.117)
        self.assertTrue(timestamp > 1362224447.117)
        self.assertTrue(timestamp3 >= 1305743832.438)
        self.assertEqual(NotImplemented, timestamp.__lt__(10))
        self.assertEqual(NotImplemented, timestamp.__le__(10))
        self.assertEqual(NotImplemented, timestamp.__gt__(10))
        self.assertEqual(NotImplemented, timestamp.__ge__(10))

        # Test for equality
        self.assertTrue(timestamp == timestamp2)
        self.assertTrue(timestamp == timestamp)
        self.assertTrue(timestamp != timestamp3)
        self.assertFalse(timestamp == 6)

        # Test for hashes
        self.assertEqual(timestamp.__hash__(), timestamp2.__hash__())
        self.assertNotEqual(timestamp.__hash__(), timestamp3.__hash__())


if __name__ == '__main__':
    unittest.main()