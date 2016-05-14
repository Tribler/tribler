import unittest

from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.timeout import Timeout


class TimeoutTestSuite(unittest.TestCase):
    """Timeout test cases."""

    def setUp(self):
        # Object creation
        self.timeout = Timeout(1462224447.117)
        self.timeout2 = Timeout(1462224447.117)
        self.timeout3 = Timeout(1305743832.438)

    def test_init(self):
        # Test for init validation
        with self.assertRaises(ValueError):
            Timeout(-1.0)

    def test_timed_out(self):
        # Test for timed out
        self.assertFalse(self.timeout.is_timed_out(Timestamp(1462224447.117)))
        self.assertFalse(self.timeout.is_timed_out(Timestamp(1262224447.117)))
        self.assertTrue(self.timeout.is_timed_out(Timestamp(1462224448.117)))

    def test_conversion(self):
        # Test for conversions
        self.assertEqual(1462224447.117, float(self.timeout))
        self.assertEqual('2016-05-02 23:27:27.117000', str(self.timeout))

    def test_hash(self):
        # Test for hashes
        self.assertEqual(self.timeout.__hash__(), self.timeout2.__hash__())
        self.assertNotEqual(self.timeout.__hash__(), self.timeout3.__hash__())


if __name__ == '__main__':
    unittest.main()