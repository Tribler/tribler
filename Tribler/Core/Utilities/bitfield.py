# Written by Bram Cohen, Uoti Urpala, and John Hoffman
# see LICENSE.txt for license information

from functools import reduce

try:
    True
except:
    True = 1
    False = 0
    bool = lambda x: not not x

try:
    sum([1])
    negsum = lambda a: len(a) - sum(a)
except:
    negsum = lambda a: reduce(lambda x, y: x + (not y), a, 0)


def _int_to_booleans(x):
    r = []
    for i in range(8):
        r.append(bool(x & 0x80))
        x <<= 1
    return tuple(r)

lookup_table = []
reverse_lookup_table = {}
for i in xrange(256):
    x = _int_to_booleans(i)
    lookup_table.append(x)
    reverse_lookup_table[x] = chr(i)


class Bitfield:

    def __init__(self, length=None, bitstring=None, copyfrom=None, fromarray=None, calcactiveranges=False):
        """
        STBSPEED
        @param calcactivetanges   Calculate which parts of the piece-space
        are non-zero, used an optimization for hooking in whilst live streaming.
        Only works in combination with bitstring parameter.
        """

        self.activeranges = []

        if copyfrom is not None:
            self.length = copyfrom.length
            self.array = copyfrom.array[:]
            self.numfalse = copyfrom.numfalse
            return
        if length is None:
            raise ValueError("length must be provided unless copying from another array")
        self.length = length
        if bitstring is not None:
            extra = len(bitstring) * 8 - length
            if extra < 0 or extra >= 8:
                raise ValueError
            t = lookup_table
            r = []

            chr0 = chr(0)
            inrange = False
            startpiece = 0
            countpiece = 0
            for c in bitstring:
                r.extend(t[ord(c)])

                # STBSPEED
                if calcactiveranges:
                    if c != chr0:
                        # Non-zero value, either start or continuation of range
                        if inrange:
                            # Stay in activerange
                            pass
                        else:
                            # Start activerange
                            startpiece = countpiece
                            inrange = True
                    else:
                        # Zero, either end or continuation of zeroness
                        if inrange:
                            # End of activerange
                            self.activeranges.append((startpiece, countpiece))
                            inrange = False
                        else:
                            # Stay in zero
                            pass
                    countpiece += 8

            if calcactiveranges:
                if inrange:
                    # activerange ended at end of piece space
                    self.activeranges.append((startpiece, min(countpiece, self.length - 1)))

            if extra > 0:
                if r[-extra:] != [0] * extra:
                    raise ValueError
                del r[-extra:]
            self.array = r
            self.numfalse = negsum(r)

        elif fromarray is not None:
            self.array = fromarray
            self.numfalse = negsum(self.array)
        else:
            self.array = [False] * length
            self.numfalse = length

    def __setitem__(self, index, val):
        val = bool(val)
        self.numfalse += self.array[index] - val
        self.array[index] = val

    def __getitem__(self, index):
        return self.array[index]

    def __len__(self):
        return self.length

    def tostring(self):
        booleans = self.array
        t = reverse_lookup_table
        s = len(booleans) % 8
        r = [t[tuple(booleans[x:x + 8])] for x in xrange(0, len(booleans) - s, 8)]
        if s:
            r += t[tuple(booleans[-s:] + ([0] * (8 - s)))]
        return ''.join(r)

    def complete(self):
        return not self.numfalse

    def copy(self):
        return self.array[:self.length]

    def toboollist(self):
        bools = [False] * self.length
        for piece in range(0, self.length):
            bools[piece] = self.array[piece]
        return bools

    def get_active_ranges(self):
        # STBSPEED
        return self.activeranges

    def get_numtrue(self):
        return self.length - self.numfalse


def test_bitfield():
    try:
        x = Bitfield(7, 'ab')
        assert False
    except ValueError:
        pass
    try:
        x = Bitfield(7, 'ab')
        assert False
    except ValueError:
        pass
    try:
        x = Bitfield(9, 'abc')
        assert False
    except ValueError:
        pass
    try:
        x = Bitfield(0, 'a')
        assert False
    except ValueError:
        pass
    try:
        x = Bitfield(1, '')
        assert False
    except ValueError:
        pass
    try:
        x = Bitfield(7, '')
        assert False
    except ValueError:
        pass
    try:
        x = Bitfield(8, '')
        assert False
    except ValueError:
        pass
    try:
        x = Bitfield(9, 'a')
        assert False
    except ValueError:
        pass
    try:
        x = Bitfield(7, chr(1))
        assert False
    except ValueError:
        pass
    try:
        x = Bitfield(9, chr(0) + chr(0x40))
        assert False
    except ValueError:
        pass
    assert Bitfield(0, '').tostring() == ''
    assert Bitfield(1, chr(0x80)).tostring() == chr(0x80)
    assert Bitfield(7, chr(0x02)).tostring() == chr(0x02)
    assert Bitfield(8, chr(0xFF)).tostring() == chr(0xFF)
    assert Bitfield(9, chr(0) + chr(0x80)).tostring() == chr(0) + chr(0x80)
    x = Bitfield(1)
    assert x.numfalse == 1
    x[0] = 1
    assert x.numfalse == 0
    x[0] = 1
    assert x.numfalse == 0
    assert x.tostring() == chr(0x80)
    x = Bitfield(7)
    assert len(x) == 7
    x[6] = 1
    assert x.numfalse == 6
    assert x.tostring() == chr(0x02)
    x = Bitfield(8)
    x[7] = 1
    assert x.tostring() == chr(1)
    x = Bitfield(9)
    x[8] = 1
    assert x.numfalse == 8
    assert x.tostring() == chr(0) + chr(0x80)
    x = Bitfield(8, chr(0xC4))
    assert len(x) == 8
    assert x.numfalse == 5
    assert x.tostring() == chr(0xC4)
