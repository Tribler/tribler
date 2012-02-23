from Tribler.Core.dispersy.decorator import Constructor, constructor

# a cycle is defined as a 60.0 second period
CYCLE_SIZE = 5.0

class EffortHistory(Constructor):
    @constructor(int, float)
    def _init_size_origin(self, size, origin):
        """
        Construct empty using SIZE.

        SIZE: number of bits in BYTES.
        ORIGIN: the current time.
        ORIGIN: float timestamp.
        """
        assert isinstance(size, int)
        assert isinstance(origin, float)
        assert size % 8 == 0
        self._size = size
        self._origin = origin
        self._bits = 0L

    @constructor(long, int, float)
    def _init_bits_size_origin(self, bits, size, origin):
        """
        Construct using BITS and SIZE.

        BITS: long containing the binary bits.
        SIZE: number of bits in BYTES.
        ORIGIN: float timestamp.
        """
        assert isinstance(bits, long)
        assert isinstance(size, int)
        assert size % 8 == 0
        assert not bits & 2**(size - 1)
        assert isinstance(origin, float)
        self._bits = bits
        self._size = size
        self._origin = origin

    @constructor(str, int, float)
    def _init_bytes_size_origin(self, bytes_, size, origin):
        """
        Construct using BYTES and SIZE.

        BYTES: string containing the binary bits.
        SIZE: number of bits in BYTES.
        ORIGIN: float timestamp.
        """
        assert isinstance(bytes_, str)
        assert 0 < len(bytes_)
        assert isinstance(size, int)
        assert size % 8 == 0
        assert isinstance(origin, float)
        self._size = size
        self._origin = origin
        self._bits = long(sum(ord(bytes_[i]) << (i*8) for i in xrange(min(len(bytes_), size/8))))

    @property
    def size(self):
        "Size in bits."
        return self._size

    @property
    def origin(self):
        "Time of most recent update, starting point of least significant bit."
        return self._origin

    @property
    def long(self):
        "Bits as a long integer."
        return self._bits

    @property
    def bytes(self):
        "Bits as a byte string."
        return "".join(chr((self._bits & (0xff << c)) >> c) for c in xrange(0, self._size, 8))

    def set(self, origin):
        """
        """
        assert isinstance(origin, float)
        assert self._origin <= origin
        difference = int((origin - self._origin) / CYCLE_SIZE)
        if difference:
            self._origin = origin

            # shift
            self._bits <<= difference

            # remove now obsolete bits
            self._bits &= 2**(self._size - 1)

            # set last bit ACTIVE
            self._bits |= 1

            return True

        else:
            if self._bits & 1:
                return False
            else:
                self._bits |= 1
                return True

    # def update(self, origin, shift, active):
    #     """
    #     Shift and update the bit string.

    #     The difference between ORIGIN and self._ORIGIN will determine how many cycles have passed.
    #     A 1 or 0 (depending on SHIFT) is added for every cycle, except the last, that has passed.
    #     A 1 or 0 (depending on ACTIVE) is added for the last cycle that passed.
    #     """
    #     assert isinstance(origin, float)
    #     assert self._origin <= origin
    #     assert isinstance(shift, bool)
    #     assert isinstance(active, bool)
    #     difference = int((origin - self._origin) / CYCLE_SIZE)
    #     if difference:
    #         self._origin = origin

    #         # shift
    #         self._bits <<= difference

    #         # remove now obsolete bits
    #         self._bits &= 2**self._size - 1

    #         # set SHIFT
    #         if shift:
    #             self._bits |= (2**(difference-1) - 1) << 1

    #         # set ACTIVE
    #         if active:
    #             self._bits |= 1

if __debug__:
    def check_results():
        passed = "\n".join(results) == """0.0 0b0
60.0 0b1
120.0 0b11
180.0 0b111
240.0 0b1111
300.0 0b11111
360.0 0b111111
420.0 0b1111111
480.0 0b11111111
540.0 0b111111111
0.0 0b0
120.0 0b1
240.0 0b101
360.0 0b10101
480.0 0b1010101
0.0 0b0
180.0 0b1
360.0 0b1001
540.0 0b1001001
0.0 0b0
60.0 0b1
120.0 0b11
180.0 0b111
240.0 0b1111
300.0 0b11111
360.0 0b111111
420.0 0b1111111
480.0 0b11111111
540.0 0b111111111
0.0 0b0
120.0 0b11
240.0 0b1111
360.0 0b111111
480.0 0b11111111
0.0 0b0
180.0 0b111
360.0 0b111111
540.0 0b111111111
0.0 0b0
60.0 0b0
120.0 0b0
180.0 0b0
240.0 0b0
300.0 0b0
360.0 0b0
420.0 0b0
480.0 0b0
540.0 0b0
0.0 0b0
120.0 0b10
240.0 0b1010
360.0 0b101010
480.0 0b10101010
0.0 0b0
180.0 0b110
360.0 0b110110
540.0 0b110110110"""
        print "PASSED?", passed

    def result(*args):
        line = " ".join(str(arg) for arg in args)
        results.append(line)
        print line

    def main():
        h = EffortHistory(32, 0.0)
        for now in xrange(0, int(10 * CYCLE_SIZE), int(CYCLE_SIZE)):
            now = float(now)
            h.update(now)
            result(now, bin(h._bits))

        h = EffortHistory(32, 0.0)
        for now in xrange(0, int(10 * CYCLE_SIZE), int(CYCLE_SIZE*2)):
            now = float(now)
            h.update(now)
            result(now, bin(h._bits))

        h = EffortHistory(32, 0.0)
        for now in xrange(0, int(10 * CYCLE_SIZE), int(CYCLE_SIZE*3)):
            now = float(now)
            h.update(now)
            result(now, bin(h._bits))

        h = EffortHistory(32, 0.0)
        for now in xrange(0, int(10 * CYCLE_SIZE), int(CYCLE_SIZE)):
            now = float(now)
            h.update(now, shift=True)
            result(now, bin(h._bits))

        h = EffortHistory(32, 0.0)
        for now in xrange(0, int(10 * CYCLE_SIZE), int(CYCLE_SIZE*2)):
            now = float(now)
            h.update(now, shift=True)
            result(now, bin(h._bits))

        h = EffortHistory(32, 0.0)
        for now in xrange(0, int(10 * CYCLE_SIZE), int(CYCLE_SIZE*3)):
            now = float(now)
            h.update(now, shift=True)
            result(now, bin(h._bits))

        h = EffortHistory(32, 0.0)
        for now in xrange(0, int(10 * CYCLE_SIZE), int(CYCLE_SIZE)):
            now = float(now)
            h.update(now, shift=True, active=False)
            result(now, bin(h._bits))

        h = EffortHistory(32, 0.0)
        for now in xrange(0, int(10 * CYCLE_SIZE), int(CYCLE_SIZE*2)):
            now = float(now)
            h.update(now, shift=True, active=False)
            result(now, bin(h._bits))

        h = EffortHistory(32, 0.0)
        for now in xrange(0, int(10 * CYCLE_SIZE), int(CYCLE_SIZE*3)):
            now = float(now)
            h.update(now, shift=True, active=False)
            result(now, bin(h._bits))

    if __name__ == "__main__":
        results = []
        main()
        check_results()
