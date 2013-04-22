import logging
logger = logging.getLogger(__name__)

from binascii import hexlify, unhexlify

from Tribler.dispersy.decorator import Constructor, constructor

# a cycle is defined as a N second period
CYCLE_SIZE = 60.0 * 30

# the number of bits used per history
BIT_COUNT = 64 * 8
assert BIT_COUNT % 8 == 0

class EffortHistory(Constructor):
    @constructor(float)
    def _init_bits_origin(self, origin):
        """
        Construct empty history.

        ORIGIN: the current time.
        ORIGIN: float timestamp.
        """
        assert isinstance(origin, float)
        self._long = 0L
        self._origin = origin

    @constructor(long, float)
    def _init_long_bits_origin(self, long_, origin):
        """
        Construct using LONG_.

        LONG_: long containing the binary bits.
        ORIGIN: float timestamp.
        """
        assert isinstance(long_, long)
        assert isinstance(origin, float)
        self._long = long_
        self._origin = origin

    @constructor(str, float)
    def _init_bytes_bits_origin(self, bytes_, origin):
        """
        Construct using BYTES.

        BYTES: string containing the binary long_.
        ORIGIN: float timestamp.
        """
        assert isinstance(bytes_, str)
        assert 0 < len(bytes_)
        assert isinstance(origin, float)
        self._origin = origin
        self._long = long(hexlify(bytes_[::-1]), 16)

    @property
    def bits(self):
        "Size in bits."
        return BIT_COUNT

    @property
    def origin(self):
        "Time of most recent update, starting point of least significant bit."
        return self._origin

    @property
    def cycle(self):
        "Cycle of the most recent update, starting point of least significant bit."
        return long(self._origin / CYCLE_SIZE)

    @property
    def long(self):
        "Bits as a long integer."
        return self._long

    @property
    def bytes(self):
        "Bits as a byte string."
        hex_ = "%x" % self._long
        return (unhexlify(hex_)[::-1]) if len(hex_) % 2 == 0 else (unhexlify("0" + hex_)[::-1])

    def set(self, origin):
        """
        """
        assert isinstance(origin, float)
        difference = int(origin / CYCLE_SIZE) - int(self._origin / CYCLE_SIZE)
        logger.debug("difference %d (%d seconds)", difference, origin - self._origin)
        if origin < self._origin:
            logger.warning("currently it is not possible to set bits in the past")

        if difference > 0:
            if __debug__:
                BEFORE = self._long

            self._origin = origin

            # shift
            self._long <<= difference

            # remove now obsolete bits
            self._long &= (2**BIT_COUNT - 1)

            # set last bit ACTIVE
            self._long |= 1

            if __debug__:
                AFTER = self._long
                logger.debug("%s -> %s (bits: %d)", bin(BEFORE), bin(AFTER), BIT_COUNT)

            return True

        else:
            if self._long & 1:
                return False
            else:
                self._long |= 1
                return True
