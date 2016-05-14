import unittest

from Tribler.community.market.core.timestamp import Timestamp
from Tribler.community.market.core.timeout import Timeout


class TimeoutTestSuite(unittest.TestCase):
    """Timeout test cases."""

    def test_timeout(self):
        # Object creation
        timeout = Timeout(1462224447.117)
        timeout2 = Timeout(1462224447.117)
        timeout3 = Timeout(1305743832.438)

        # Test for init validation
        with self.assertRaises(ValueError):
            Timeout(-1.0)

        # Test for timed out
        self.assertFalse(timeout.is_timed_out(Timestamp(1462224447.117)))
        self.assertFalse(timeout.is_timed_out(Timestamp(1262224447.117)))
        self.assertTrue(timeout.is_timed_out(Timestamp(1462224448.117)))

        # Test for conversions
        self.assertEqual(1462224447.117, float(timeout))
        self.assertEqual('2016-05-02 23:27:27.117000', str(timeout))

        # Test for hashes
        self.assertEqual(timeout.__hash__(), timeout2.__hash__())
        self.assertNotEqual(timeout.__hash__(), timeout3.__hash__())


if __name__ == '__main__':
    unittest.main()