from Tribler.dispersy.logger import get_logger
logger = get_logger(__name__)

from binascii import hexlify, unhexlify

# a cycle is defined as a N second period
CYCLE_SIZE = 60.0 * 30

# the number of bits used per history
BIT_COUNT = 64 * 8
assert BIT_COUNT % 8 == 0


class EffortHistory(object):

    """
    The EffortHistory constructor takes parameters that are interpreted differently, depending on
    their type.  The following type combination, and their interpretations, are possible:

    - EffortHistory(float:origin)

      Will create an empty history.

    - EffortHistory(long:bits, float:origin)

      Will create a history from existing bits.

    - EffortHistory(str:bytes, float:origin)

      Will create a history from existing bytes.
    """

    @classmethod
    def _overload_constructor_arguments(cls, args):
        # matches: EffortHistory(float:origin)
        if len(args) == 1 and isinstance(args[0], float):
            long_ = 0
            origin = args[0]

        # matches: EffortHistory(long:bits, float:origin)
        elif len(args) == 2 and isinstance(args[0], long) and isinstance(args[1], float):
            long_ = args[0]
            origin = args[1]

        # matches: EffortHistory(str:bytes, float:origin)
        elif len(args) == 2 and isinstance(args[0], str) and isinstance(args[1], float):
            assert len(args[0]) > 0, len(args[0])
            long_ = long(hexlify(args[0][::-1]), 16)
            origin = args[1]

        else:
            raise RuntimeError("Unknown combination of argument types %s" % str([type(arg) for arg in args]))

        return long_, origin

    def __init__(self, *args):
        # get constructor arguments
        self._long, self._origin = self._overload_constructor_arguments(args)
        assert isinstance(self._long, (int, long)), type(self._long)
        assert isinstance(self._origin, float), type(self._origin)

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
            self._long &= (2 ** BIT_COUNT - 1)

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
