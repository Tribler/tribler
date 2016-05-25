import unittest

from Tribler.community.market.ttl import Ttl


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
            Ttl(3)
        with self.assertRaises(ValueError):
            Ttl('1')

    def test_default(self):
        # Test for default init
        self.assertEqual(2, int(Ttl.default()))

    def test_conversion(self):
        # Test for conversions
        self.assertEqual(0, int(self.ttl))
        self.assertEqual(2, int(self.ttl2))
        self.assertEqual("0", str(self.ttl))
        self.assertEqual("2", str(self.ttl2))

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

    def test_equality(self):
        # Test for equality
        self.assertTrue(self.ttl == self.ttl)
        self.assertTrue(self.ttl2 == self.ttl3)
        self.assertFalse(self.ttl == self.ttl2)
        self.assertEquals(NotImplemented, self.ttl.__eq__(0))

    def test_non_equality(self):
        # Test for non equality
        self.assertTrue(self.ttl != self.ttl3)
        self.assertFalse(self.ttl2 != self.ttl3)
        self.assertFalse(self.ttl.__ne__(0))

    def test_hash(self):
        # Test for hashes
        self.assertEqual(self.ttl2.__hash__(), self.ttl3.__hash__())
        self.assertNotEqual(self.ttl.__hash__(), self.ttl2.__hash__())
        self.ttl4.make_hop()
        self.assertEqual(self.ttl.__hash__(), self.ttl4.__hash__())


if __name__ == '__main__':
    unittest.main()
