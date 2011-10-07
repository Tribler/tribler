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

from array import array
from hashlib import sha1, sha256, sha384, sha512, md5
from math import ceil, log, exp
from struct import unpack, pack

from decorator import Constructor, constructor

if __debug__:
    from dprint import dprint
    from time import time

def _make_hashfuncs(num_slices, num_bits, prefix):
    if num_bits >= (1 << 31):
        fmt_code, chunk_size = 'Q', 8
    elif num_bits >= (1 << 15):
        fmt_code, chunk_size = 'L', 4
    else:
        fmt_code, chunk_size = 'H', 2
    total_hash_bits = 8 * num_slices * chunk_size
    if total_hash_bits > 384:
        hashfn = sha512
    elif total_hash_bits > 256:
        hashfn = sha384
    elif total_hash_bits > 160:
        hashfn = sha256
    elif total_hash_bits > 128:
        hashfn = sha1
    else:
        hashfn = md5
    fmt = "!" + fmt_code * (hashfn().digest_size // chunk_size)
    num_salts, extra = divmod(num_slices, len(fmt))
    if extra:
        num_salts += 1
    salts = [hashfn(hashfn(pack('!L', i)).digest() + prefix) for i in xrange(num_salts)]
    def _make_hashfuncs_helper(key):
        assert isinstance(key, str), "KEY must be a binary string"
        rval = []
        for salt in salts:
            h = salt.copy()
            h.update(key)
            rval.extend(uint % num_bits for uint in unpack(fmt, h.digest()))

        # if __debug__:
        #     if len(rval) > num_slices:
        #         print "Wasted", len(rval) - num_slices, "cycles"

        del rval[num_slices:]
        return rval
    return _make_hashfuncs_helper

class BloomFilter(Constructor):
    """
    Implements a space-efficient probabilistic data structure.

    There are three overloaded constructors:
     - __init__(CAPACITY, ERROR_RATE)
     - __init__(NUM_SLICES, BITS_PER_SLICE)
     - __init__(DATA, OFFSET)

    CAPACITY: this BloomFilter must be able to store at least CAPACITY elements while maintaining no
    more than ERROR_RATE chance of false positives.

    ERROR_RATE: the error_rate of the filter returning false positives. This determines the filters
    capacity. Inserting more than capacity elements greatly increases the chance of false positives.

    NUM_SLICES: the number of slices.  More slices makes the BloomFilter more fault tolerant as well
    as bigger.  Each slice has its own hash function, and each key added to the BloomFilter will
    (potentially) set one bit per slice.

    BITS_PER_SLICE: the number of bits in each slice.

    DATA: the stream contains binary data for a BloomFilter.

    OFFSET: the start of the bloomfiter in DATA

    >>> # use CAPACITY, ERROR_RATE constructor
    >>> b = BloomFilter(100000, 0.001)
    >>> b.add("test")
    True
    >>> "test" in b
    True

    >>> # use NUM_SLICES, BITS_PER_SLICE constructor
    >>> b = BloomFilter(1, 1024)
    >>> b.add("test")
    True
    >>> "test" in b
    True

    >>> # use DATA, OFFSET constructor
    >>> b = BloomFilter(100000, 0.001)
    >>> b.add("test")
    >>> data = str(b)
    >>> c = BloomFilter(data, 0)
    >>> "test" in c
    True
    """

    @constructor((int, long), (int, long))
    def _init_size_(self, num_slices, bits_per_slice, prefix=""):
        """
        Initialize a new BloomFilter instance.

        Each time an item is added to the BloomFilter a bit will be set in each slice.  Therefore,
        having more slices will reduce the chance of false positives at the cost of using more bits.

        @param num_slices: The number of slices.
        @type num_slices: int or long

        @param bits_per_slice: The number of bits per slice.
        @type bits_per_slice: int or long

        @param prefix: A prefix used for each key.
        @type prefix: string
        """
        assert isinstance(num_slices, (int, long))
        assert num_slices > 0
        assert isinstance(bits_per_slice, (int, long))
        assert bits_per_slice > 0
        assert isinstance(prefix, str)
        assert len(prefix) <= 255
        
        self._num_slices = num_slices
        self._bits_per_slice = bits_per_slice
        
        self._prefix = prefix
        self._make_hashes = _make_hashfuncs(num_slices, bits_per_slice, prefix)
        self._bytes = array("B", (0 for _ in xrange(int(ceil(num_slices * bits_per_slice / 8.0)))))

    @constructor((int, long), float)
    def _init_capacity_(self, capacity, error_rate, prefix=""):
        """
        Initialize a new BloomFilter instance.

        The optimal number of slices and slice size is choosen based on how many items are expected
        to be stored in the BloomFilter and how many false positives are allowed to occur.

        @param capacity: How many items are expected to be stored in the BloomFilter.  Storing more
         than this value will result in higher chances for false positives.
        @type capacity: (int, long)

        @param error_rate: The chance a false positive occurs given that there are no more than
         capacity items in the BloomFilter.
        @type error_rate: float

        @param prefix: A prefix used for each key.
        @type prefix: string
        """
        assert isinstance(capacity, (int, long))
        assert isinstance(error_rate, float)
        assert 0 < error_rate < 1, "Error_Rate must be between 0 and 1"
        assert capacity > 0, "Capacity must be > 0"
        assert isinstance(prefix, str)
        assert len(prefix) <= 255
        
        
        self._capacity = capacity
        self._num_slices = int(ceil(log(1 / error_rate, 2)))
        assert self._num_slices > 0
        
        # the error_rate constraint assumes a fill rate of 1/2
        # so we double the capacity to simplify the API
        
        bits = ceil (-(capacity * log(error_rate)) / (log(2) ** 2))  
        self._bits_per_slice = int(bits / self._num_slices)
        assert self._bits_per_slice > 0
        
        self._prefix = prefix
        self._make_hashes = _make_hashfuncs(self._num_slices, self._bits_per_slice, prefix)
        self._bytes = array("B", (0 for _ in xrange(int(ceil(self._num_slices * self._bits_per_slice / 8.0)))))

    @constructor(float, (int, long))
    def _init_length(self, error_rate, bits, prefix=""):
        """
        Initialize a new BloomFilter instance.

        The optimal number of slices and slice size is choosen based on how many false positives are
        allowed to occur and the total number of bits available to the bloom filter.

        @param error_rate: The chance a false positive occurs given that there are no more than
         capacity items in the BloomFilter.
        @type error_rate: float

        @param bits: The number of bits available to the bloom filter.  Must be a multiple of 8.
        @type bits: int or long

        @param prefix: A prefix used for each key.
        @type prefix: string
        """
        assert isinstance(error_rate, float)
        assert 0 < error_rate < 1, "Error_Rate must be between 0 and 1"
        assert isinstance(bits, (int, long))
        assert bits > 0, "Bits must be > 0"
        assert isinstance(prefix, str)
        assert len(prefix) <= 255
        
        #from Scalable Bloom filters
        #n ~= bits * ((ln 2)^2) / | ln error_rate |
        #k = log2(1 / error_rate)
        self._capacity = bits * ((log(2) ** 2) / abs(log(error_rate)))
        
        self._num_slices = int(ceil(log(1 / error_rate, 2)))
        assert self._num_slices > 0
        
        self._bits_per_slice = bits / self._num_slices
        assert self._bits_per_slice > 0
        
        self._prefix = prefix
        self._make_hashes = _make_hashfuncs(self._num_slices, self._bits_per_slice, prefix)
        self._bytes = array("B", (0 for _ in xrange(int(ceil(self._num_slices * self._bits_per_slice / 8.0)))))

    @constructor(str, (int, long), (int, long))
    def _init_load_(self, data, num_slices, bits_per_slice, offset=0, prefix=""):
        """
        Initialize a new BloomFilter instance.

        Loads an existing BloomFilter from a string representation.

        @param data: The binary sting containing the BloomFilter.
        @type data: string

        @param num_slices: The number of slices.
        @type num_slices: int or long

        @param bits_per_slice: The number of bits per slice.
        @type bits_per_slice: int or long

        @param offset: The first index in the binary string where the BloomFilter starts.
        @type offset: int or long
        @note: offset should have a default value of zero.  However, currently the Constructor
               overloading does not support this.

        @param prefix: A prefix used for each key.
        @type prefix: string
        """
        assert isinstance(data, str)
        assert isinstance(num_slices, (int, long))
        assert num_slices > 0
        assert isinstance(bits_per_slice, (int, long))
        assert bits_per_slice > 0
        assert len(data) >= offset + ceil(num_slices * bits_per_slice / 8.0), (len(data), offset + ceil(num_slices * bits_per_slice / 8.0))
        assert isinstance(offset, (int, long))
        assert isinstance(prefix, str)
        assert len(prefix) <= 255
        
        self._num_slices = num_slices
        self._bits_per_slice = bits_per_slice
        
        self._prefix = prefix
        self._make_hashes = _make_hashfuncs(num_slices, bits_per_slice, prefix)
        self._bytes = array("B", data[offset:offset+int(ceil(num_slices*bits_per_slice/8.0))])

    @property
    def error_rate(self):
        """
        Calculate the optimal error rate from the current settings.
        @rtype: float
        """
        p = exp(- self._num_slices * self._capacity/self.size)
        return (1 - p) ** self._num_slices

    @property
    def capacity(self):
        """
        Calculate the optimal capacity from the current setting.
        @rtype: long
        """
        
        #from Scalable Bloom filters
        #n ~= bits * ((ln 2)^2) / | ln error_rate |
        return int(self.size * ((log(2) ** 2) / abs(log(self.error_rate))))

    @property
    def num_slices(self):
        return self._num_slices

    @property
    def bits_per_slice(self):
        return self._bits_per_slice

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
        Returns the raw bloom filter bytes.
        @rtype: string
        """
        return self._bytes.tostring()

    @property
    def size(self):
        """
        The size of the bloom filter in bits, i.e. how many bits the bloom filter uses.
        @rtype: int or long
        """
        return self._num_slices * self._bits_per_slice

    def __contains__(self, key):
        """
        Tests a key's membership in this bloom filter.

        >>> b = BloomFilter(capacity=100)
        >>> b.add("hello")
        >>> "hello" in b
        True

        @param key: The key to test.
        @type key: string

        @return: True when key is contained in the BloomFilter.
        @rtype: bool
        """
        assert isinstance(key, str), "Key must be a binary string"
        bits_per_slice = self._bits_per_slice
        bytes = self._bytes
        offset = 0
        for i in self._make_hashes(key):
            if not bytes[(offset + i) / 8] & 1<<(offset + i) % 8:
                return False
            offset += bits_per_slice
        return True

    def add(self, key):
        """
        Adds a key to this bloom filter.

        >>> b = BloomFilter(capacity=100)
        >>> b.add("hello")
        >>> b.add("hello")

        @param key: The key to add.
        @type key: string
        """
        assert isinstance(key, str), "Key must be a binary string"
        bytes = self._bytes
        bits_per_slice = self._bits_per_slice
        offset = 0
        for i in self._make_hashes(key):
            bytes[(offset + i) / 8] |=  1<<(offset + i) % 8
            offset += bits_per_slice

    def clear(self):
        """
        Sets all bits in the filter to zero.
        """
        self._bytes = array("B", (0 for _ in xrange(int(ceil(self._num_slices * self._bits_per_slice / 8.0)))))

    def and_occurrence(self, other):
        """
        Counts the number of bits that are set at the same indexes in this and the other
        BloomFilter.

        >>> b = BloomFilter(binary_to_string("01110"))
        >>> o = BloomFilter(binary_to_string("01000"))
        >>> b.and_occurrence(o)             #  ^
        >>> 1

        In order to compare, both BloomFilters need to be compatible.  In other words, they need to
        have the same number of slices and number of bits per slice.

        @param other: The other BloomFilter to compare with.
        @type other: BloomFilter

        @return: The number of bits counted.
        @rtype: int or long
        @raise ValueError: When both BloomFilters are are incompatible, i.e. have different number
         of slices or bits per slice.
        """
        assert isinstance(other, BloomFilter)
        if not (self._num_slices == other._num_slices and self._bits_per_slice == other._bits_per_slice and self._prefix == other._prefix):
            raise ValueError("Both bloom filters need to have the same size and prefix")

        bits = (1, 2, 4, 8, 16, 32, 64, 128)
        count = 0
        for c in (a & b for a, b in zip(self._bytes, other._bytes)):
            count += len(filter(lambda bit: bit & c, bits))
        return count

    def xor_occurrence(self, other):
        """
        Counts the number of bits that are set in either this of the other BloomFilter, at the same
        indexes, but not in both at the same time.

        >>> b = BloomFilter(binary_to_string("01110"))
        >>> o = BloomFilter(binary_to_string("01000"))
        >>> b.xor_occurrence(o)             #   ^^
        >>> 2

        In order to compare, both BloomFilters need to be compatible.  In other words, they need to
        have the same number of slices and number of bits per slice.

        @param other: The other BloomFilter to compare with.
        @type other: BloomFilter

        @return: The number of bits counted.
        @rtype: int or long
        @raise ValueError: When both BloomFilters are are incompatible, i.e. have different number
         of slices or bits per slice.
        """
        assert isinstance(other, BloomFilter)
        if not (self._num_slices == other._num_slices and self._bits_per_slice == other._bits_per_slice and self._prefix == other._prefix):
            raise ValueError("Both bloom filters need to have the same size and prefix")

        bits = (1, 2, 4, 8, 16, 32, 64, 128)
        count = 0
        for c in (a ^ b for a, b in zip(self._bytes, other._bytes)):
            count += len(filter(lambda bit: bit & c, bits))
        return count

    def bic_occurrence(self, other):
        """
        Counts the number of bits that are biconditional, i.e. have the same value in both this and
        the other BloomFilter, at the same indexes.

        >>> b = BloomFilter(binary_to_string("01110"))
        >>> o = BloomFilter(binary_to_string("01000"))
        >>> b.bic_occurrence(o)             # ^^  ^
        >>> 3

        In order to compare, both BloomFilters need to be compatible.  In other words, they need to
        have the same number of slices and number of bits per slice.

        @param other: The other BloomFilter to compare with.
        @type other: BloomFilter

        @return: The number of bits counted.
        @rtype: int or long
        @raise ValueError: When both BloomFilters are are incompatible, i.e. have different number
         of slices or bits per slice.
        """
        assert isinstance(other, BloomFilter)
        if not (self._num_slices == other._num_slices and self._bits_per_slice == other._bits_per_slice and self._prefix == other._prefix):
            raise ValueError("Both bloom filters need to have the same size and prefix")

        bits = (1, 2, 4, 8, 16, 32, 64, 128)
        count = 0
        for c in (a ^ b for a, b in zip(self._bytes, other._bytes)):
            count += len(filter(lambda bit: bit & c, bits))
        return (self._num_slices * self._bits_per_slice) - count

    def __and__(self, other):
        """
        Create a new BloomFilter by merging this and the other BloomFilter using the AND operator.

        In order to merge, both BloomFilters need to be compatible.  In other words, they need to
        have the same number of slices and number of bits per slice.

        @param other: The other BloomFilter to merge with.
        @type other: BloomFilter

        @return: A new BloomFilter.
        @rtype: BloomFilter
        @raise ValueError: When both BloomFilters are are incompatible, i.e. have different number
         of slices or bits per slice.
        """
        assert isinstance(other, BloomFilter)
        if not (self._num_slices == other._num_slices and self._bits_per_slice == other._bits_per_slice and self._prefix == other._prefix):
            raise ValueError("Both bloom filters need to have the same size and prefix")
        return BloomFilter(pack("!LL", self._num_slices, self._bits_per_slice) + array("B", [i&j for i, j in zip(self._bytes, other._bytes)]).tostring(), 0)

    def __xor__(self, other):
        """
        Create a new BloomFilter by merging this and the other BloomFilter using the XOR operator.

        In order to merge, both BloomFilters need to be compatible.  In other words, they need to
        have the same number of slices and number of bits per slice.

        @param other: The other BloomFilter to merge with.
        @type other: BloomFilter

        @return: A new BloomFilter.
        @rtype: BloomFilter
        @raise ValueError: When both BloomFilters are are incompatible, i.e. have different number
         of slices or bits per slice.
        """
        assert isinstance(other, BloomFilter)
        if not (self._num_slices == other._num_slices and self._bits_per_slice == other._bits_per_slice and self._prefix == other._prefix):
            raise ValueError("Both bloom filters need to have the same size and prefix")
        return BloomFilter(pack("!LL", self._num_slices, self._bits_per_slice) + array("B", [i^j for i, j in zip(self._bytes, other._bytes)]).tostring(), 0)

    # def __str__(self):
    #     """
    #     Create a string representation of the BloomFilter.

    #     @return: The string representation.
    #     @rtype: string
    #     @note: This method will change in the future.  The num_slices and bits_per_slice will be
    #      removed and the method renamed.
    #     """
    #     return pack("!LLB", self._num_slices, self._bits_per_slice, len(self._prefix)) + self._prefix + self._bytes.tostring()


class FasterBloomFilter(object):
    def __init__(self, f, m, prefix = ''):
        self._f = f 
        self._m = m
        self._prefix = prefix
          
        #calculate others
        self._n = int(m * ((log(2) ** 2) / abs(log(f))))
        self._k = int(ceil(log(2) * (m / self._n)))
        
        #determine hash function
        if m >= (1 << 31):
            fmt_code, chunk_size = 'Q', 8
        elif m >= (1 << 15):
            fmt_code, chunk_size = 'L', 4
        else:
            fmt_code, chunk_size = 'H', 2
        
        #we need atmost chunk_size * k bits from our hash function
        bits_required = chunk_size * self._k * 8
        assert bits_required <= 512, 'Combining multiple hashfunctions is not implemented, cannot create a hash for %d bits'%bits_required

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
        self._fmt = '!' + (fmt_code * self._k) + ('x' * (hashfn().digest_size - bits_required/8))
        self._salt = hashfn(prefix)
        
        #python documentation states: a long is a signed number of arbitrary length
        self.filter = 0L
    
    def _hashes(self, key):
        h = self._salt.copy()
        h.update(key)
        
        digest = h.digest()
        indexes = unpack(self._fmt, digest)
        return [index % self._m for index in indexes]
        
    def add(self, key):
        bits = 0L
        for pos in self._hashes(key):
            bits |= 1 << pos
        
        self.filter |= bits
      
    def __contains__(self, key):
        filter = self.filter
        for pos in self._hashes(key):
            if not filter & (1 << pos):
                return False 
        return True
    
    
    @property
    def error_rate(self):
        return self._f

    @property
    def capacity(self):
        return self._n
    
    @property
    def size(self):
        return self._m

    @property
    def num_slices(self):
        return -1

    @property
    def bits_per_slice(self):
        return -1

    @property
    def prefix(self):
        """
        The prefix.
        @rtype: string
        """
        return self._prefix

    @property
    def bytes(self):
        return bin(self.filter)

if __debug__:
    def _performance_test():
        def test2(bits, count, constructor = BloomFilter):
            generate_begin = time()
            ok = 0
            data = [(i, sha1(str(i)).digest()) for i in xrange(count)]
            create_begin = time()
            bloom = constructor(0.0001, bits)
            fill_begin = time()
            for i, h in data:
                if i % 2 == 0:
                    bloom.add(h)
            check_begin = time()
            for i, h in data:
                if (h in bloom) == (i % 2 == 0):
                    ok += 1
            write_begin = time()
            string = str(bloom)
            write_end = time()

            print "generate: {generate:.1f}; create: {create:.1f}; fill: {fill:.1f}; check: {check:.1f}; write: {write:.1f}".format(generate=create_begin-generate_begin, create=fill_begin-create_begin, fill=check_begin-fill_begin, check=write_begin-check_begin, write=write_end-write_begin)
            print string.encode("HEX")[:100], "{len} bytes; ({ok}/{total} ~{part:.0%})".format(len=len(string), ok=ok, total=count, part=1.0*ok/count)

        def test(bits, count, constructor = BloomFilter):
            ok = 0
            create_begin = time()
            bloom = constructor(0.0001, bits)
            fill_begin = time()
            for i in xrange(count):
                if i % 2 == 0:
                    bloom.add(str(i))
            check_begin = time()
            for i in xrange(count):
                if (str(i) in bloom) == (i % 2 == 0):
                    ok += 1
            write_begin = time()
            string = str(bloom)
            write_end = time()

            print "create: {create:.1f}; fill: {fill:.1f}; check: {check:.1f}; write: {write:.1f}".format(create=fill_begin-create_begin, fill=check_begin-fill_begin, check=write_begin-check_begin, write=write_end-write_begin)
            print string.encode("HEX")[:100], "{len} bytes; ({ok}/{total} ~{part:.0%})".format(len=len(string), ok=ok, total=count, part=1.0*ok/count)

        b = BloomFilter(100, 0.0001)
        b.add("Hello")
        data = str(b)

        #c = BloomFilter(data, 0)
        #assert "Hello" in c
        #assert not "Bye" in c
        
        test2(10, 10,FasterBloomFilter)
        test2(10, 100,FasterBloomFilter)
        test2(100, 100,FasterBloomFilter)
        test2(100, 1000,FasterBloomFilter)
        test2(1000, 1000,FasterBloomFilter)
        test2(1000, 10000,FasterBloomFilter)
        test2(10000, 10000,FasterBloomFilter)
        test2(10000, 100000,FasterBloomFilter)
        
        test(10, 10,FasterBloomFilter)
        test(10, 100,FasterBloomFilter)
        test(100, 100,FasterBloomFilter)
        test(100, 1000,FasterBloomFilter)
        test(1000, 1000,FasterBloomFilter)
        test(1000, 10000,FasterBloomFilter)
        test(10000, 10000,FasterBloomFilter)
        test(10000, 100000,FasterBloomFilter)
        test(100000, 100000,FasterBloomFilter)
        test(100000, 1000000,FasterBloomFilter)
        

        #test2(10, 10)
        #test2(10, 100)

# generate: 0.0; create: 0.0; fill: 0.0; check: 0.0; write: 0.0
# 0a0000001d000000241400480001840684024080408012800008012424018008a0401001080280008500241000 45 bytes; (10/10 ~100%)
# generate: 0.0; create: 0.0; fill: 0.0; check: 0.0; write: 0.0
# 0a0000001d000000bfbedf7fbafff4bffff7fdb7efdffe8df74f9fff6dbffb7bed7fdaf9ae76dfefffebffdb03 45 bytes; (90/100 ~90%)

        test2(100, 100)
        test2(100, 1000)

# generate: 0.0; create: 0.0; fill: 0.0; check: 0.0; write: 0.0
# 0a0000002001000002050100400001820008020388084422108050c0b41440804a003044204020082804000049820c880420 368 bytes; (100/100 ~100%)
# generate: 0.0; create: 0.0; fill: 0.0; check: 0.0; write: 0.0
# 0a000000200100009eedefcc77df2fff1feffe5fdeeefebffefe7fddffb77bf1cff574ddbedffafdbffffdf6fdef7f9ebf7f 368 bytes; (919/1000 ~92%)

        test2(1000, 1000)
        test2(1000, 10000)

# generate: 0.0; create: 0.0; fill: 0.0; check: 0.0; write: 0.0
# 0a0000003c0b0000a203040502001140c0000010840900420a06152400042000004222010090000022861000824010102001 3603 bytes; (1000/1000 ~100%)
# generate: 0.0; create: 0.0; fill: 0.1; check: 0.1; write: 0.0
# 0a0000003c0b0000fad3ffeffffdfb7efb5efffcfefffceffb7fffb7df3ffff99f7bffd5fdd7f65d76e7ff2f9feffcda7fff 3603 bytes; (9279/10000 ~93%)

        test2(10000, 10000)
        test2(10000, 100000)

# generate: 0.0; create: 0.0; fill: 0.1; check: 0.1; write: 0.0
# 0a00000054700000205286262400208041034085040005524802d8667048204220001214805020502002600408060080d009 35953 bytes; (10000/10000 ~100%)
# generate: 0.2; create: 0.0; fill: 0.7; check: 1.3; write: 0.0
# 0a00000054700000fbfffffeffffffbbfffffff7edbfffffff7fdffff7dbffffffffffbf9efafffbfffff5dddbdfffffd7ff 35953 bytes; (92622/100000 ~93%)

        #test(10, 10)
        #test(10, 100)

# create: 0.0; fill: 0.0; check: 0.0; write: 0.0
# 0a0000001d00000081012001030240322100040400440c510024402060400100010410088c0005020a18020100 45 bytes; (10/10 ~100%)
# create: 0.0; fill: 0.0; check: 0.0; write: 0.0
# 0a0000001d000000ebfff7fbefdedfbbeffffdeee7ddbf7fb7fdff77ffff77f5d74dff9efdffffffef7f9e3f03 45 bytes; (92/100 ~92%)

        test(100, 100)
        test(100, 1000)

# create: 0.0; fill: 0.0; check: 0.0; write: 0.0
# 0a0000002001000000108007008010210218120a0802824800806a20911008424200a00a0000114000100009466002820916 368 bytes; (100/100 ~100%)
# create: 0.0; fill: 0.0; check: 0.0; write: 0.0
# 0a000000200100007ff7f777fabadfffd7fddfdf29dfdefe77fc7bedfffc7df37e7ff9ffbbfff57fb7feffcfdffd7ffffdbf 368 bytes; (915/1000 ~92%)

        test(1000, 1000)
        test(1000, 10000)

# create: 0.0; fill: 0.0; check: 0.0; write: 0.0
# 0a0000003c0b00000146869100238482200450100090040002000010000006244000000c4a0141040402210802000c208010 3603 bytes; (1000/1000 ~100%)
# create: 0.0; fill: 0.1; check: 0.1; write: 0.0
# 0a0000003c0b0000f7ffffbbdbfbefffeffff7ff5cffff27f6defffadff76ef5fbfbecffdfd7fdee77f7ffdffea07dfebbdf 3603 bytes; (9279/10000 ~93%)

        test(10000, 10000)
        test(10000, 100000)

# create: 0.0; fill: 0.1; check: 0.1; write: 0.0
# 0a00000054700000130050403102c002410c410200a100700200cc0c0007620100142c408c4a82080082000a866d1818a211 35953 bytes; (10000/10000 ~100%)
# create: 0.0; fill: 0.8; check: 1.4; write: 0.0
# 0a000000547000009ffefff7fdffecff7dffffbeeefffffefffdffeef9efffffebff7ffdffffbfffd7ffeeefff7ffdfbffff 35953 bytes; (92520/100000 ~93%)

        test(100000, 100000)
        test(100000, 1000000)
        

    def _taste_test():
        def pri(f, m, invert=False):
            set_bits = 0
            for c in f._bytes.tostring():
                s = "{0:08d}".format(int(bin(ord(c))[2:]))
                for bit in s:
                    if invert:
                        if bit == "0":
                            bit = "1"
                        else:
                            bit = "0"
                    if bit == "1":
                        set_bits += 1
                print s,
            percent = 100 * set_bits / f.bits
            print "= {0:2d} bits or {1:2d}%:".format(set_bits, percent), m

        def gen(l, m):
            if len(l) <= 10:
                for e in l:
                    f = BloomFilter(NUM_SLICES, BITS_PER_SLICE)
                    f.add(e)
                    pri(f, e)
            f = BloomFilter(NUM_SLICES, BITS_PER_SLICE)
            map(f.add, l)
            if len(l) <= 10:
                pri(f, m + ": " + ", ".join(l))
            else:
                pri(f, m + ": " + l[0] + "..." + l[-1])
            return f

        NUM_SLICES, BITS_PER_SLICE = 1, 25

        # a = gen(["kittens", "puppies"], "User A")
        # b = gen(["beer", "bars"], "User B")
        # c = gen(["puppies", "beer"], "User C")

        # a = gen(map(str, xrange(0, 150)), "User A")
        # b = gen(map(str, xrange(100, 250)), "User B")
        # c = gen(map(str, xrange(200, 350)), "User C")

        a = gen(map(str, xrange(0, 10)), "User A")
        b = gen(map(str, xrange(5, 15)), "User B")
        c = gen(map(str, xrange(10, 20)), "User C")

        if True:
            print
            pri(a&b, "A AND B --> 50%")
            pri(a&c, "A AND C -->  0%")
            pri(b&c, "B AND C --> 50%")
        if True:
            print
            pri(a^b, "A XOR B --> 50%", invert=True)
            pri(a^c, "A XOR C -->  0%", invert=True)
            pri(b^c, "B XOR C --> 50%", invert=True)

    def _test_documentation():
        alice = ["cake", "lemonade", "kittens", "puppies"]
        for x in alice:
            b = BloomFilter(1, 32)
            b.add(x)
            dprint(x)
            dprint(b._bytes.tostring(), binary=1)

        bob = ["cake", "lemonade", "beer", "pubs"]

        carol = ["beer", "booze", "women", "pubs"]
        for x in carol:
            b = BloomFilter(1, 32)
            b.add(x)
            dprint(x)
            dprint(b._bytes.tostring(), binary=1)

        a = BloomFilter(1, 32)
        map(a.add, alice)
        dprint(alice)
        dprint(a._bytes.tostring(), binary=1)

        b = BloomFilter(1, 32)
        map(b.add, bob)
        dprint(bob)
        dprint(b._bytes.tostring(), binary=1)

        c = BloomFilter(1, 32)
        map(c.add, carol)
        dprint(carol)
        dprint(c._bytes.tostring(), binary=1)

        dprint("Alice bic Bob: ", a.bic_occurrence(b))
        dprint("Alice bic Carol: ", a.bic_occurrence(c))
        dprint("Bob bic Carol: ", b.bic_occurrence(c))

        # b2 = BloomFilter(10, 0.8)
        # map(b2.add, t2)

        # dprint(t1)
        # dprint(str(b1), binary=1)

        # dprint(t2)
        # dprint(str(b2), binary=1)

    def _test_occurrence():
        a = BloomFilter(1, 16)
        b = BloomFilter(1, 16)
        assert a.and_occurrence(b) == 0
        assert a.xor_occurrence(b) == 0
        assert a.and_occurrence(a) == 0
        assert a.xor_occurrence(a) == 0
        assert b.and_occurrence(a) == 0
        assert b.xor_occurrence(a) == 0
        assert b.and_occurrence(b) == 0
        assert b.xor_occurrence(b) == 0

        a.add("a1")
        a.add("a2")
        a.add("a3")
        b.add("b1")
        b.add("b2")

        dprint(a._bytes.tostring(), binary=1)
        dprint(b._bytes.tostring(), binary=1)

        assert a.and_occurrence(b) == 1
        assert a.xor_occurrence(b) == 3

    def _test_save_load():
        a = BloomFilter(1000, 0.1)
        data = ["%i" % i for i in xrange(1000)]
        map(a.add, data)

        print a._num_slices, a._bits_per_slice

        binary = str(a)
        open("bloomfilter-out.data", "w+").write(binary)
        print "Write binary:", len(binary)

        try:
            binary = open("bloomfilter-in.data", "r").read()
        except IOError:
            print "Input file unavailable"
        else:
            print "Read binary:", len(binary)
            b = BloomFilter(binary, 0)
            print b._num_slices, b._bits_per_slice

            for d in data:
                assert d in b
            for d in ["%i" % i for i in xrange(10000, 1100)]:
                assert not d in b

    def _test_false_positives(constructor = BloomFilter):
        for error_rate in [0.0001, 0.001, 0.01, 0.1, 0.4]:
            a = constructor(error_rate, 1024*8)
            p(a)
            
            data = ["%i" % i for i in xrange(int(a.capacity))]
            map(a.add, data)

            errors = 0
            for i in xrange(100000):
                if "X%i" % i in a:
                    errors += 1

            print "Errors:", errors, "/", i + 1, " ~ ", errors / (i + 1.0)
            print

    def _test_prefix_false_positives(constructor = BloomFilter):
        for error_rate in [0.0001, 0.001, 0.01, 0.1, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9]:
            a = constructor(error_rate, 10374, prefix="A")
            b = constructor(error_rate, 10374, prefix="B")
            c = constructor(error_rate, 10374, prefix="C")
            d = constructor(error_rate, 10374, prefix="D")
            p(a)
            print "Estimated errors:", a.error_rate, "->", a.error_rate * b.error_rate, "->", a.error_rate * b.error_rate * c.error_rate, "->", a.error_rate * b.error_rate * c.error_rate * d.error_rate
            
            #we fill each bloomfilter up to its capacity
            data = ["%i" % i for i in xrange(a.capacity)]
            map(a.add, data)
            map(b.add, data)
            map(c.add, data)
            map(d.add, data)

            errors = 0
            two_errors = 0
            three_errors = 0
            four_errors = 0
            
            #we check what happens if we check twice the capacity
            for i in xrange(a.capacity * 2):
                if "X%i" % i in a:
                    errors += 1
                    if "X%i" % i in b:
                        two_errors += 1
                        if "X%i" % i in c:
                            three_errors += 1
                            if "X%i" % i in d:
                                four_errors += 1

            print "Errors:", errors, "~", errors / (i + 1.0), "Two-Errors:", two_errors, "~", two_errors / (i + 1.0), "Three-Errors:", three_errors, "~", three_errors / (i + 1.0), four_errors, "~", four_errors / (i + 1.0)
            print

    def _test_performance():
        from time import clock
        from struct import pack
        from random import random

        from database import Database

        class TestDatabase(Database):
            def check_database(self, *args):
                pass

        db = TestDatabase.get_instance(u"test.db")
        
        DATA_COUNT = 1000
        RUN_COUNT = 1000
        
        db.execute(u"CREATE TABLE data10 (id INTEGER PRIMARY KEY AUTOINCREMENT, public_key TEXT, global_time INTEGER)")
        db.execute(u"CREATE TABLE data500 (id INTEGER PRIMARY KEY AUTOINCREMENT, packet TEXT)")
        db.execute(u"CREATE TABLE data1500 (id INTEGER PRIMARY KEY AUTOINCREMENT, packet TEXT)")
        db.executemany(u"INSERT INTO data10 (public_key, global_time) VALUES (?, ?)", ((buffer("".join(chr(int(random() * 256)) for _ in xrange(83))), int(random() * 2**32)) for _ in xrange(DATA_COUNT)))
        db.executemany(u"INSERT INTO data500 (packet) VALUES (?)", ((buffer("".join(chr(int(random() * 256)) for _ in xrange(500))),) for _ in xrange(DATA_COUNT)))
        db.executemany(u"INSERT INTO data1500 (packet) VALUES (?)", ((buffer("".join(chr(int(random() * 256)) for _ in xrange(1500))),) for _ in xrange(DATA_COUNT)))

        b10 = BloomFilter(1000, 0.1)
        for public_key, global_time in db.execute(u"SELECT public_key, global_time FROM data10"):
            b10.add(str(public_key) + pack("!Q", global_time))

        b500 = BloomFilter(1000, 0.1)
        for packet, in db.execute(u"SELECT packet FROM data500"):
            b500.add(str(packet))

        b1500 = BloomFilter(1000, 0.1)
        for packet, in db.execute(u"SELECT packet FROM data1500"):
            b1500.add(str(packet))
            
        check10 = []
        check500 = []
        check1500 = []

        for _ in xrange(RUN_COUNT):
            start = clock()
            for public_key, global_time in db.execute(u"SELECT public_key, global_time FROM data10"):
                if not str(public_key) + pack("!Q", global_time) in b10:
                    raise RuntimeError("err")
            end = clock()
            check10.append(end - start)

            start = clock()
            for packet, in db.execute(u"SELECT packet FROM data500"):
                if not str(packet) in b500:
                    raise RuntimeError("err")
            end = clock()
            check500.append(end - start)

            start = clock()
            for packet, in db.execute(u"SELECT packet FROM data1500"):
                if not str(packet) in b1500:
                    raise RuntimeError("err")
            end = clock()
            check1500.append(end - start)
            
        print DATA_COUNT, "*", RUN_COUNT, "=", DATA_COUNT * RUN_COUNT
        print "check"
        print "10  ", sum(check10)
        print "500 ", sum(check500)
        print "1500", sum(check1500)
            
    def p(b, postfix=""):
        print "capacity:", b.capacity, "error-rate:", b.error_rate, "num-slices:", b.num_slices, "bits-per-slice:", b.bits_per_slice, "bits:", b.size, "bytes:", b.size / 8, "packet-bytes:", b.size / 8 + 51 + 60 + 16 + 8, postfix

    if __name__ == "__main__":
        #_performance_test()
        # _taste_test()
        # _test_occurrence()
        # _test_documentation()
        # _test_save_load()
        _test_performance()
        # _test_false_positives()
        # _test_false_positives(FasterBloomFilter)
        # _test_prefix_false_positives()
        # _test_prefix_false_positives(FasterBloomFilter)

        # MTU = 1500 # typical MTU
        # # MTU = 576 # ADSL
        # DISP = 51 + 60 + 16 + 8
        # BITS = 9583 # currently used bloom filter size
        # # BITS = (MTU - 20 - 8 - DISP) * 8 # size allowed by MTU (typical header)
        # BITS = (MTU - 60 - 8 - DISP) * 8 # size allowed by MTU (max header)

        # # b1 = BloomFilter(1000, 0.01)
        # # p(b1)
        # # b2 = BloomFilter(0.01, b1.size)
        # # p(b2)
        # b3 = BloomFilter(0.001, BITS)
        # p(b3)
        # b3 = BloomFilter(0.01, BITS)
        # p(b3)
        # b3 = BloomFilter(0.1, BITS)
        # p(b3)
        # b4 = BloomFilter(0.5, BITS)
        # p(b4)
