# disable E0611, No name %r in module %r.  pylint is unable to correctly assess the content of hashlib
# pylint: disable=E0611

# disable E1103, %s %r has no %r member (but some types could not be inferred).  Because pylint can not correctly assess
# the content of hashlib is can not assess its members either.
# pylint: disable=E1103

"""
This module provides the bloom filter support.

The Bloom filter, conceived by Burton Howard Bloom in 1970, is a space-efficient probabilistic data
structure that is used to test whether an element is a member of a set.  False positives are
possible, but false negatives are not.  Elements can be added to the set, but not removed (though
this can be addressed with a counting filter).  The more elements that are added to the set, the
larger the probability of false positives.

Initial Bloomfilter implementation based on pybloom by Jay Baird <jay@mochimedia.com> and Bob
Ippolito <bob@redivi.com>.  Simplified, and optimized to use just python code.

@author: Boudewijn Schoon
@organization: Technical University Delft
@contact: dispersy@frayja.com
"""
from __future__ import absolute_import, division

import logging
from binascii import hexlify, unhexlify
from hashlib import md5, sha1, sha256, sha384, sha512
from math import ceil, log
from struct import Struct

from six import binary_type, integer_types

logger = logging.getLogger(__name__)


class BloomFilter(object):

    """
    A Bloom filter, conceived by Burton Howard Bloom in 1970 is a space-efficient probabilistic data structure that is
    used to test whether an element is a member of a set.  False positive matches are possible, but false negatives are
    not; i.e. a query returns either "inside set (may be wrong)" or "definitely not in set".  Elements can be added to
    the set, but not removed. The more elements that are added to the set, the larger the probability of false
    positives.

    The BloomFilter constructor takes parameters that are interpreted differently, depending on their type.  The
    following type combination, and their interpretations, are possible:

    - BloomFilter(int:m_size, float:f_error_rate, str:prefix="")

      Will create a BloomFilter instance that is m_size bits large with approximately f_error_rate chance for false
      positives.  Typically this is used to create a bloom filter where the size it can occupy is limited or fixed.
      Note that m_size must be a multiple of 8.

    - BloomFilter(float:f_error_rate, int:n_capacity, str:prefix="")

      Will create a BloomFilter instance with approximately f_error_rate chance for false positives when n_capacity keys
      are added.  The m_size, i.e. bits required for storage, is approximated from the f_error_rate and n_capacity.

    - BloomFilter(str:bytes, int:k_functions, str:prefix="")

      Will create a BloomFilter instance from a binary string and a number of functions.  Typically this is used to
      retrieve a bloom filter that was serialised.  For example:

      original = BloomFilter(128, 0.25)
      original.add_keys(str(i) for i in xrange(100))
      storage = (original.bytes, original.functions, original.prefix)
      # storage can be written to disk, socket, etc
      clone = BloomFilter(storage[0], storage[1], storage[2])
    """

    @staticmethod
    def _get_k_functions(m_size, n_capacity):
        return int(ceil(log(2) * m_size // n_capacity))

    @staticmethod
    def _get_n_capacity(m_size, f_error_rate):
        return int(m_size * (log(2) ** 2 / abs(log(f_error_rate))))

    @classmethod
    def _overload_constructor_arguments(cls, args, kargs):
        # matches: BloomFilter(str:bytes, int:k_functions, str:prefix="")
        if len(args) >= 2 and isinstance(args[0], binary_type) and isinstance(args[1], int):
            bytes_ = args[0]
            m_size = len(bytes_) * 8
            k_functions = args[1]
            prefix = kargs.get("prefix", args[2] if len(args) >= 3 else b"")
            assert 0 < len(bytes_), len(bytes_)
            logger.debug("bloom filter based on %d bytes and k_functions %d", len(bytes_), k_functions)
            filter_ = int(hexlify(bytes_[::-1]), 16)

        # matches: BloomFilter(int:m_size, float:f_error_rate, str:prefix="")
        elif len(args) >= 2 and isinstance(args[0], int) and isinstance(args[1], float):
            m_size = args[0]
            f_error_rate = args[1]
            prefix = kargs.get("prefix", args[2] if len(args) >= 3 else b"")
            assert 0 < m_size, m_size
            assert m_size % 8 == 0, "size must be a multiple of eight (%d)" % m_size
            assert 0.0 < f_error_rate < 1.0, f_error_rate
            logger.debug("constructing bloom filter based on m_size %d bits and f_error_rate %f", m_size, f_error_rate)
            k_functions = cls._get_k_functions(m_size, cls._get_n_capacity(m_size, f_error_rate))
            filter_ = 0

        # matches: BloomFilter(float:f_error_rate, int:n_capacity, str:prefix="")
        elif len(args) >= 2 and isinstance(args[0], float) and isinstance(args[1], int):
            f_error_rate = args[0]
            n_capacity = args[1]
            prefix = kargs.get("prefix", args[2] if len(args) >= 3 else b"")
            assert 0.0 < f_error_rate < 1.0, f_error_rate
            assert 0 < n_capacity, n_capacity
            logger.debug("constructing bloom filter based on f_error_rate %f and %d n_capacity", f_error_rate,
                         n_capacity)
            m_size = int(ceil(abs((n_capacity * log(f_error_rate)) // (log(2) ** 2)) // 8.0) * 8)
            k_functions = cls._get_k_functions(m_size, n_capacity)
            filter_ = 0

        else:
            raise RuntimeError("Unknown combination of argument types %s" % str([type(arg) for arg in args]))

        return m_size, k_functions, prefix, filter_

    def __init__(self, *args, **kargs):
        self._logger = logging.getLogger(self.__class__.__name__)

        # get constructor arguments required to build the bloom filter
        self._m_size, self._k_functions, self._prefix, self._filter = self._overload_constructor_arguments(args, kargs)

        assert isinstance(self._m_size, int), type(self._m_size)
        assert 0 < self._m_size, self._m_size
        assert self._m_size % 8 == 0, "size must be a multiple of eight (%d)" % self._m_size
        assert isinstance(self._k_functions, int), type(self._k_functions)
        assert 0 < self._k_functions <= self._m_size, [self._k_functions, self._m_size]
        assert isinstance(self._prefix, binary_type), type(self._prefix)
        assert 0 <= len(self._prefix) < 256, len(self._prefix)
        assert isinstance(self._filter, integer_types), type(self._filter)

        # determine hash function
        if self._m_size >= (1 << 31):
            fmt_code, chunk_size = "Q", 8
        elif self._m_size >= (1 << 15):
            fmt_code, chunk_size = "L", 4
        else:
            fmt_code, chunk_size = "H", 2

        # we need at most chunk_size * k bits from our hash function
        bits_required = chunk_size * self._k_functions * 8
        assert bits_required <= 512, \
            "Combining multiple hashfunctions is not implemented, cannot create a hash for %d bits" % bits_required

        if bits_required > 384:
            hashfn = sha512
        elif bits_required > 256:
            hashfn = sha384
        elif bits_required > 160:
            hashfn = sha256
        elif bits_required > 128:
            hashfn = sha1
        else:
            hashfn = md5

        self._fmt_unpack = Struct("".join((">",
                                           fmt_code * self._k_functions,
                                           "x" * (hashfn().digest_size - bits_required // 8)))).unpack
        self._salt = hashfn(self._prefix)

    def add(self, key):
        """
        Add KEY to the BloomFilter.
        """
        filter_ = self._filter
        hash_ = self._salt.copy()
        hash_.update(key)
        for pos in self._fmt_unpack(hash_.digest()):
            filter_ |= 1 << (pos % self._m_size)
        self._filter = filter_

    def add_keys(self, keys):
        """
        Add a sequence of KEYS to the BloomFilter.
        """
        filter_ = self._filter
        salt_copy = self._salt.copy
        m_size = self._m_size
        fmt_unpack = self._fmt_unpack

        for key in keys:
            assert isinstance(key, binary_type)
            hash_ = salt_copy()
            hash_.update(key)

            # 04/05/12 Boudewijn: using a list instead of a generator is significantly faster.
            # while generators are more memory efficient, this list will be relatively short.
            # 07/05/12 Niels: using no list at all is even more efficient/faster
            for pos in fmt_unpack(hash_.digest()):
                filter_ |= 1 << (pos % m_size)

        self._filter = filter_

    def clear(self):
        """
        Set all bits in the filter to zero.
        """
        self._filter = 0

    def __contains__(self, key):
        filter_ = self._filter
        m_size_ = self._m_size

        hash_ = self._salt.copy()
        hash_.update(key)

        for pos in self._fmt_unpack(hash_.digest()):
            if not filter_ & (1 << (pos % m_size_)):
                return False
        return True

    def not_filter(self, iterator):
        """
        Yields all tuples in iterator where the first element in the tuple is NOT in the bloom
        filter.
        """
        filter_ = self._filter
        salt_copy = self._salt.copy
        m_size = self._m_size
        fmt_unpack = self._fmt_unpack

        for tup in iterator:
            assert isinstance(tup, tuple)
            assert len(tup) > 0
            assert isinstance(tup[0], binary_type)
            hash_ = salt_copy()
            hash_.update(tup[0])

            # 04/05/12 Boudewijn: using a list instead of a generator is significantly faster.
            # while generators are more memory efficient, this list will be relatively short.
            # 07/05/12 Niels: using no list at all is even more efficient/faster
            for pos in fmt_unpack(hash_.digest()):
                if not filter_ & (1 << (pos % m_size)):
                    yield tup
                    break

    def get_capacity(self, f_error_rate):
        """
        Returns the capacity given a certain error rate.
        @rtype: int
        """
        assert isinstance(f_error_rate, float)
        assert 0 < f_error_rate < 1
        return self._get_n_capacity(self._m_size, f_error_rate)

    def get_bits_checked(self):
        """
        Returns the number of bits in the bloom filter that are set.
        @rtype: int
        """
        # get_bits_checked does not take any parameters, hence it should be a property like size, functions, etc.
        self._logger.warning("get_bits_checked function is deprecated, please use the bits_checked property")
        return self.bits_checked

    @property
    def bits_checked(self):
        """
        The number of bits in the bloom filter that are set.
        @rtype: int
        """
        return sum(1 if self._filter & (1 << i) else 0 for i in range(self._m_size))

    @property
    def size(self):
        """
        The size of the bloom filter in bits (m).
        @rtype: int
        """
        return self._m_size

    @property
    def functions(self):
        """
        The number of functions used for each item (k).
        """
        return self._k_functions

    @property
    def prefix(self):
        """
        The prefix.
        @rtype: string
        """
        return self._prefix

    @property
    def bytes(self):
        """
        The binary representation of the bits in the bloom filter.  Note that to reconstruct the bloom filter, not the
        bytes as well as the number of functions are required.
        @rtype: string
        """
        # hex should be m_size/4, hex is 16 instead of 8 -> hence half the number of "hexes" in m_size
        hex_ = '%x' % self._filter
        padding = '0' * (self._m_size // 4 - len(hex_))
        return unhexlify(padding + hex_)[::-1]
