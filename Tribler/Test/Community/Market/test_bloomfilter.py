from __future__ import absolute_import, division

from unittest import TestCase

from six import binary_type
from six.moves import xrange

from Tribler.community.market.core.bloomfilter import BloomFilter


class TestBloomFilter(TestCase):

    def test_fixed_size_constructor(self):
        """
        Testing BloomFilter(int:m_size, float:f_error_rate, str:prefix="")
        """
        blooms = [BloomFilter(128 * 8, 0.25),
                  BloomFilter(128 * 8, 0.25, b""),
                  BloomFilter(128 * 8, 0.25, prefix=b"")]

        for bloom in blooms:
            bloom.add_keys(binary_type(i) for i in xrange(100))
            self.assertEqual(bloom.size, 128 * 8)
            self.assertEqual(len(bloom.bytes), 128)
            self.assertEqual(bloom.prefix, b"")

        blooms = [BloomFilter(128 * 8, 0.25, b"p"),
                  BloomFilter(128 * 8, 0.25, prefix=b"p")]

        for bloom in blooms:
            bloom.add_keys(binary_type(i) for i in xrange(100))
            self.assertEqual(bloom.size, 128 * 8)
            self.assertEqual(len(bloom.bytes), 128)
            self.assertEqual(bloom.prefix, b"p")

    def test_adaptive_size_constructor(self):
        """
        Testing BloomFilter(float:f_error_rate, int:n_capacity, str:prefix="")
        """
        blooms = [BloomFilter(0.25, 142),
                  BloomFilter(0.25, 142, b""),
                  BloomFilter(0.25, 142, prefix=b"")]

        for bloom in blooms:
            bloom.add_keys(binary_type(i) for i in xrange(100))
            self.assertEqual(bloom.prefix, b"")

        blooms = [BloomFilter(0.25, 142, b"p"),
                  BloomFilter(0.25, 142, prefix=b"p")]

        for bloom in blooms:
            bloom.add_keys(binary_type(i) for i in xrange(100))
            self.assertEqual(bloom.prefix, b"p")

    def test_load_constructor(self):
        """
        Testing BloomFilter(str:bytes, int:k_functions, str:prefix="")
        """
        bloom = BloomFilter(128 * 8, 0.25)
        bloom.add_keys(binary_type(i) for i in xrange(100))
        bytes_, functions = bloom.bytes, bloom.functions

        blooms = [BloomFilter(bytes_, functions),
                  BloomFilter(bytes_, functions, b""),
                  BloomFilter(bytes_, functions, prefix=b"")]

        for bloom in blooms:
            self.assertEqual(bloom.size, 128 * 8)
            self.assertEqual(bloom.bytes, bytes_)
            self.assertEqual(bloom.prefix, b"")
            self.assertTrue(all(binary_type(i) in bloom for i in xrange(100)))

        bloom = BloomFilter(128 * 8, 0.25, b"p")
        bloom.add_keys(binary_type(i) for i in xrange(100))
        bytes_, functions = bloom.bytes, bloom.functions

        blooms = [BloomFilter(bytes_, functions, b"p"),
                  BloomFilter(bytes_, functions, prefix=b"p")]

        for bloom in blooms:
            self.assertEqual(bloom.size, 128 * 8)
            self.assertEqual(bloom.bytes, bytes_)
            self.assertEqual(bloom.prefix, b"p")
            self.assertTrue(all(binary_type(i) in bloom for i in xrange(100)))

    def test_clear(self):
        """
        Testing BloomFilter.clear()
        """
        bloom = BloomFilter(128 * 8, 0.25)
        self.assertEqual(bloom.bits_checked, 0)
        bloom.add_keys(binary_type(i) for i in xrange(100))
        self.assertNotEqual(bloom.bits_checked, 0)
        bloom.clear()
        self.assertEqual(bloom.bits_checked, 0)

    def test_false_positives(self):
        """
        Testing false positives.
        """
        args = [(0.1, 128, b""),
                (0.2, 128, b""),
                (0.3, 128, b""),
                (0.4, 128, b""),
                (0.1, 1024, b""),
                (0.2, 1024, b""),
                (0.3, 1024, b""),
                (0.4, 1024, b""),
                (0.1, 128, b"p"),
                (0.2, 128, b"p"),
                (0.3, 128, b"p"),
                (0.4, 128, b"p"),
                (0.1, 1024, b"p"),
                (0.2, 1024, b"p"),
                (0.3, 1024, b"p"),
                (0.4, 1024, b"p")]

        for f_error_rate, n_capacity, prefix in args:
            bloom = BloomFilter(f_error_rate, n_capacity, prefix)
            bloom.add_keys(binary_type(i) for i in xrange(n_capacity))
            self.assertTrue(all(binary_type(i) in bloom for i in xrange(n_capacity)))
            false_positives = sum(binary_type(i) in bloom for i in xrange(n_capacity, n_capacity + 10000))
            self.assertAlmostEqual(1.0 * false_positives / 10000, f_error_rate, delta=0.05)
