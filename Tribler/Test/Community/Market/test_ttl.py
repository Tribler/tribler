import unittest

from Tribler.community.market.core.ttl import Ttl


class TtlTestSuite(unittest.TestCase):
    """Ttl test cases."""

    def setUp(self):
        # Object creation
        self.ttl = Ttl(0)
        self.ttl2 = Ttl(2)
        self.ttl3 = Ttl(2)
        self.ttl4 = Ttl(1)

    def test_init(self):
        # Test for init validation
        with self.assertRaises(ValueError):
            Ttl(-100)
        with self.assertRaises(ValueError):
            Ttl('1')

    def test_default(self):
        # Test for default init
        self.assertEqual(2, int(Ttl.default()))

    def test_conversion(self):
        # Test for conversions
        self.assertEqual(0, int(self.ttl))
        self.assertEqual(2, int(self.ttl2))

    def test_make_hop(self):
        # Test for make hop
        self.assertEqual(2, int(self.ttl2))
        self.ttl2.make_hop()
        self.assertEqual(1, int(self.ttl2))

    def test_is_alive(self):
        # Test for is alive
        self.assertTrue(self.ttl4.is_alive())
        self.ttl4.make_hop()
        self.assertFalse(self.ttl4.is_alive())
