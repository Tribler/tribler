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

from hashlib import sha1, sha256, sha384, sha512, md5
from math import ceil, log
from struct import unpack

from decorator import Constructor, constructor

if __debug__:
    from dprint import dprint
    from time import time

class BloomFilter(Constructor):
    def _init_(self, m_size, k_functions, prefix, filter_):
        assert isinstance(m_size, int)
        assert 0 < m_size
        assert m_size % 8 == 0, "size must be a multiple of eight (%d)" % m_size
        assert isinstance(k_functions, int)
        assert 0 < k_functions <= m_size
        assert isinstance(prefix, str)
        assert 0 <= len(prefix) < 256
        assert isinstance(filter_, long)

        self._m_size = m_size
        self._k_functions = k_functions
        self._prefix = prefix
        self._filter = filter_

        if __debug__:
            dprint("m size:      ", m_size, "    ~", m_size / 8, " bytes")
            dprint("k functions: ", k_functions)
            dprint("prefix:      ", prefix.encode("HEX"))
            dprint("filter:      ", filter_)
            hypothetical_error_rates = [0.4, 0.3, 0.2, 0.1, 0.01, 0.001, 0.0001]
            dprint("hypothetical error rate: ", " | ".join("%.4f" % hypothetical_error_rate for hypothetical_error_rate in hypothetical_error_rates))
            dprint("hypothetical capacity:   ", " | ".join("%6d" % self.get_capacity(hypothetical_error_rate) for hypothetical_error_rate in hypothetical_error_rates))
    
        # determine hash function
        if m_size >= (1 << 31):
            fmt_code, chunk_size = "Q", 8
        elif m_size >= (1 << 15):
            fmt_code, chunk_size = "L", 4
        else:
            fmt_code, chunk_size = "H", 2
        
        # we need at most chunk_size * k bits from our hash function
        bits_required = chunk_size * k_functions * 8
        assert bits_required <= 512, "Combining multiple hashfunctions is not implemented, cannot create a hash for %d bits" % bits_required

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

        self._fmt = ">" + (fmt_code * k_functions) + ("x" * (hashfn().digest_size - bits_required / 8))
        self._salt = hashfn(prefix)

    @constructor(str, int)
    def _init_bytes_k_(self, bytes_, k_functions, prefix=""):
        assert isinstance(bytes_, str)
        assert 0 < len(bytes_)
        if __debug__: dprint("constructing bloom filter based on ", len(bytes_), " bytes and k_functions ", k_functions)
        self._init_(len(bytes_) * 8, k_functions, prefix, long(sum(ord(bytes_[i]) << (i*8) for i in xrange(len(bytes_)))))

    @constructor(int, float)
    def _init_m_f(self, m_size, f_error_rate, prefix=""):
        assert isinstance(m_size, int)
        assert 0 < m_size
        assert m_size % 8 == 0, "size must be a multiple of eight (%d)" % m_size
        assert isinstance(f_error_rate, float)
        assert 0 < f_error_rate < 1
        # calculate others
        # self._n = int(m * ((log(2) ** 2) / abs(log(f))))
        # self._k = int(ceil(log(2) * (m / self._n)))
        if __debug__: dprint("constructing bloom filter based on m_size ", m_size, " bits and f_error_rate ", f_error_rate)
        self._init_(m_size, self._get_k_functions(m_size, self._get_n_capacity(m_size, f_error_rate)), prefix, 0L)
    
    def _hashes(self, key):
        h = self._salt.copy()
        h.update(key)
        return (index % self._m_size for index in unpack(self._fmt, h.digest()))
        
    def add(self, key):
        bits = 0L
        for pos in self._hashes(key):
            bits |= 1 << pos
        self._filter |= bits
      
    def clear(self):
        """
        Set all bits in the filter to zero.
        """
        self._filter = 0L

    def __contains__(self, key):
        filter_ = self._filter
        for pos in self._hashes(key):
            if not filter_ & (1 << pos):
                return False 
        return True

    def _get_k_functions(self, m_size, n_capacity):
        return int(ceil(log(2) * m_size / n_capacity))
        
    def _get_n_capacity(self, m_size, f_error_rate):
        return int(m_size * (log(2) ** 2 / abs(log(f_error_rate))))
    
    def get_capacity(self, f_error_rate):
        """
        Returns the capacity given a certain error rate.
        @rtype: int
        """
        assert isinstance(f_error_rate, float)
        assert 0 < f_error_rate < 1
        return self._get_n_capacity(self._m_size, f_error_rate)
        
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
        return "".join(chr((self._filter & (0xff << c)) >> c) for c in xrange(0, self._m_size, 8))
    
if __debug__:
    def _test_behavior():
        length = 1024
        f_error_rate = 0.15
        m_size = length * 8
        
        b = BloomFilter(m_size, f_error_rate)
        assert len(b.bytes) == length, b.bytes

        for i in xrange(1000):
            b.add(str(i))
        print b.size, b.get_capacity(f_error_rate), b.bytes.encode("HEX")

        d = BloomFilter(b.bytes, b.functions)
        assert b.size == d.size
        assert b.functions == d.functions
        assert b.bytes == d.bytes
        for i in xrange(1000):
            assert str(i) in d
        print d.size, d.get_capacity(f_error_rate), d.bytes.encode("HEX")
        
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

    # def _test_false_positives(constructor = BloomFilter):
    #     for error_rate in [0.0001, 0.001, 0.01, 0.1, 0.4]:
    #         a = constructor(error_rate, 1024*8)
    #         p(a)
            
    #         data = ["%i" % i for i in xrange(int(a.capacity))]
    #         map(a.add, data)

    #         errors = 0
    #         for i in xrange(100000):
    #             if "X%i" % i in a:
    #                 errors += 1

    #         print "Errors:", errors, "/", i + 1, " ~ ", errors / (i + 1.0)
    #         print

    def _test_false_positives(constructor = BloomFilter):
        for error_rate in [0.001, 0.01, 0.1, 0.5]:
            begin = time()
            # if constructor == BloomFilter:
            #     a = constructor(error_rate, 1024*8)
            #     capacity = a.capacity
            # else:
            a = constructor(1024*8, error_rate)
            capacity = a.get_capacity(error_rate)
            print "capacity:", capacity, " error-rate:", error_rate, "bits:", a.size, "bytes:", a.size / 8
            
            data = ["%i" % i for i in xrange(capacity)]
            map(a.add, data)

            errors = 0
            for i in xrange(200000):
                if "X%i" % i in a:
                    errors += 1
            end = time()
                    
            print "%.3f"%(end-begin), "Errors:", errors, "/", i + 1, " ~ ", errors / (i + 1.0)
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
        # print "capacity:", b.capacity, "error-rate:", b.error_rate, "num-slices:", b.num_slices, "bits-per-slice:", b.bits_per_slice, "bits:", b.size, "bytes:", b.size / 8, "packet-bytes:", b.size / 8 + 51 + 60 + 16 + 8, postfix
        print "error-rate", b.error_rate, "bits:", b.size, "bytes:", b.size / 8, "packet-bytes:", b.size / 8 + 51 + 60 + 16 + 8, postfix

    if __name__ == "__main__":
        _test_behavior()
        #_performance_test()
        # _taste_test()
        # _test_occurrence()
        # _test_documentation()
        # _test_save_load()
        # _test_performance()
        _test_false_positives()
        # _test_prefix_false_positives()
        # _test_prefix_false_positives(FasterBloomFilter)
        # _test_behavior(FasterBloomFilter)
        
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
