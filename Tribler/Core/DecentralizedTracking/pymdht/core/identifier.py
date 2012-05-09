# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

"""
This module provides the Id object and necessary tools.

"""

#binascii.hexlify() bin>hex
#int(a, 16) hex>int
#hex() int>hex

import sys
import random
import base64

import logging

logger = logging.getLogger('dht')


BITS_PER_BYTE = 8
ID_SIZE_BYTES = 20
ID_SIZE_BITS = ID_SIZE_BYTES * BITS_PER_BYTE
MAX_ID_LONG = ALL_ONES_LONG = (1 << ID_SIZE_BITS) - 1

class IdError(Exception):
    pass


class Id(object):

    """Convert a string to an Id object.
    The bin_id string's lenght must be ID_SIZE bytes (characters)
    OR an integer/long.

    You can use both binary and hexadecimal strings. Example:
    
    >>> Id(chr(0) * ID_SIZE_BYTES) == Id('0' * ID_SIZE_BYTES * 2)
    True
    
    >>> Id(chr(255) * ID_SIZE_BYTES) == Id('f' * ID_SIZE_BYTES * 2)
    True

    >>> Id(chr(0) * ID_SIZE_BYTES) == Id(0)
    True

    >>> Id(chr(255) * ID_SIZE_BYTES) == Id(MAX_ID_LONG)
    True
    
    """

    def __init__(self, hex_or_bin_id):
        self._bin_id = None
        self._bin = None
        self._hex = None
        self._bin_str = None
        self._long = None
        self._log = None
        if isinstance(hex_or_bin_id, str):
            if len(hex_or_bin_id) == ID_SIZE_BYTES:
                self._bin_id = hex_or_bin_id
            elif len(hex_or_bin_id) == ID_SIZE_BYTES*2:
                self._hex = hex_or_bin_id
                try:
                    self._bin_id = base64.b16decode(hex_or_bin_id, True)
                except:
                    raise IdError, 'input: %r' % hex_or_bin_id
        elif isinstance(hex_or_bin_id, long) or isinstance(hex_or_bin_id, int):
            if hex_or_bin_id < 0 or hex_or_bin_id > MAX_ID_LONG:
                raise IdError, 'input: %r' % hex_or_bin_id
            self._long = long(hex_or_bin_id)
            self._hex = '%040x' % self._long
            self._bin_id = base64.b16decode(self._hex, True)
        if not self._bin_id:
            raise IdError, 'input: %r' % hex_or_bin_id
        self._bin = self._bin_id

    def __hash__(self):
        return self.bin_id.__hash__()

    @property
    def bin_id(self):
        """bin_id is read-only."""
        return self._bin
 
    @property
    def bin(self):
        return self._bin

    @property
    def hex(self):
        if not self._hex:
            self._hex = base64.b16encode(self._bin)
        return self._hex

    @property
    def bin_str(self):
        if not self._bin_str:
            bin_str = bin(self.long)[2:]
            # Need to pad to get 160 bits
            self._bin_str = '0'*(ID_SIZE_BITS - len(bin_str)) + bin_str
        return self._bin_str

    @property
    def long(self):
        if not self._long:
            self._long = long(self.hex, 16)
        return self._long

    @property
    def log(self):
        if not self._log:
            if self.long == 0:
                self._log = -1
            else:
                self._log = len(bin(self.long)) - 3
        return self._log

    @property
    def prefix_len(self):
        return ID_SIZE_BITS - self.log

    def __cmp__(self, other):
        return self.long.__cmp__(other.long)
        
    def __eq__(self, other):
        return self.long == other.long

    def __ne__(self, other):
        return not self == other
        
    def __str__(self):
        return self.bin_id

    def __repr__(self):
        return '%s' % self.hex

    def distance(self, other):
        """
        Do XOR distance between two Id objects and return it as Id
        object.

        """
        return Id(self.long ^ other.long)
    
    def log_distance(self, other):
        """Return log (base 2) of the XOR distance between two Id
        objects. Return -1 when the XOR distance is 0.

        That is, this function returns 'n' when the distance between
        the two objects is [2^n, 2^(n+1)).
        When the two identifiers are equal, the distance is 0. Therefore
        log_distance is -infinity. In this case, -1 is returned.
        Example:

        >>> z = Id(chr(0) * ID_SIZE_BYTES)

        >>> # distance = 0 [-inf, 1) -> log(0) = -infinity
        >>> z.log_distance(z) 
        -1
        >>> # distance = 1 [1, 2) -> log(1) = 0
        >>> z.log_distance(Id(chr(0)*(ID_SIZE_BYTES-1)+chr(1)))
        0
        >>> # distance = 2 [2, 4) -> log(2) = 1
        >>> z.log_distance(Id(chr(0)*(ID_SIZE_BYTES-1)+chr(2)))
        1
        >>> # distance = 3 [2, 4) -> log(3) = 
        >>> z.log_distance(Id(chr(0)*(ID_SIZE_BYTES-1)+chr(3)))
        1
        >>> # distance = 4 [4, 8) -> log(2^2) = 2
        >>> z.log_distance(Id(chr(0)*(ID_SIZE_BYTES-1)+chr(4)))
        2
        >>> # distance = 5 [4, 8) -> log(5) = 2
        >>> z.log_distance(Id(chr(0)*(ID_SIZE_BYTES-1)+chr(5)))
        2
        >>> # distance = 6  [4, 8) -> log(6) = 2
        >>> z.log_distance(Id(chr(0)*(ID_SIZE_BYTES-1)+chr(6)))
        2
        >>> # distance = 7  [4, 8) -> log(7) = 2
        >>> z.log_distance(Id(chr(0)*(ID_SIZE_BYTES-1)+chr(7)))
        2
        >>> # distance = 128 = 2^(8*0+7)  [128, 256) -> log(7^2) = 7
        >>> z.log_distance(Id(chr(0)*(ID_SIZE_BYTES-1)+chr(128)))
        7
        >>> # distance = 2^(8*18+8) = 2^148+8 -> log(1) = 152
        >>> z.log_distance(Id(chr(1)+chr(0)*(ID_SIZE_BYTES-1)))
        152
        >>> # distance = 2^(8*19+1) = 2^159 -> log(1) = 159
        >>> z.log_distance(Id(chr(128)+chr(0)*(ID_SIZE_BYTES-1)))
        159

        """
        return self.distance(other).log

    def get_prefix(self, prefix_len):
        return self.bin_str[:prefix_len]

    def get_bit(self, index):
        if self.long & (1 << (ID_SIZE_BITS - index - 1)):
            return 1
        else:
            return 0

    
    def DD_order_closest(self, id_list):
        """Return a list with the Id objects in 'id_list' ordered
        according to the distance to self. The closest id first.
        
        The original list is not modified.

        """
        id_list_copy = id_list[:]
        max_distance = ID_SIZE_BITS + 1
        log_distance_list = [] 
        for element in id_list:
            log_distance_list.append(self.log_distance(element))

        result = []
        for _ in range(len(id_list)):
            lowest_index = None
            lowest_distance = max_distance
            for j in range(len(id_list_copy)):
                if log_distance_list[j] < lowest_distance:
                    lowest_index = j
                    lowest_distance = log_distance_list[j]
            result.append(id_list_copy[lowest_index])
            del log_distance_list[lowest_index]
            del id_list_copy[lowest_index]
        return result
    
    def generate_close_id(self, log_distance):
        assert log_distance < ID_SIZE_BITS
        if log_distance < 0:
            return self
        byte_num, bit_num = divmod(log_distance, BITS_PER_BYTE)
        byte_index = len(self.bin_id) - byte_num - 1 # -1 correction
        int_byte = ord(self.bin_id[byte_index])
        import sys
        # Flip bit
        int_byte = int_byte ^ (1 << bit_num)
        for i in range(bit_num):
            # Put bit to 0
            int_byte = int_byte & (255 - (1 << i))
            # Replace bit for random bit
            int_byte = int_byte + (random.randint(0, 1) << i)
        id_byte = chr(int_byte)
        # Produce random ending bytes
        end_bytes = ''.join([chr(random.randint(0, 255)) \
                                      for _ in xrange(byte_index + 1, ID_SIZE_BYTES)])
        bin_id = self.bin_id[:byte_index] +\
            id_byte + end_bytes
        result = Id(bin_id)
        return result 

    def set_bit(self, index, value):
        if value:
            long_id = self.long | (1 << index)
        else:
            long_id = self.long & (ALL_ONES_LONG ^ (1 << index))
        return Id(long_id)

MAX_ID = Id(MAX_ID_LONG)

    
class RandomId(Id):

    """Create a random Id object."""
    def __init__(self, bin_prefix=''):
        padding_len = ID_SIZE_BITS - len(bin_prefix)
        long_id = 0
        if bin_prefix:
            long_id = long(bin_prefix, 2)
            long_id = long_id << padding_len
        long_id = long_id + random.randint(0, (1 << padding_len) - 1)
        Id.__init__(self, long_id)
