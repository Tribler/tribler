"""
Packaging utilities for speed and correctness.

To gain parsing speed, messages are delimited by newline characters.
This allows for near-trivial message parsing.

To allow for non-escaped messages, messages are prepended with their
data length. This allows the parser to skip newline delimiters which
occur before the expected message size has been met.
"""

import struct


def pack_data(data):
    """
    Generic data wrapper

    Data is wrapped between the data length (8 bytes) and
    a newline.

    :param data: the data to pack
    :type data: str
    :return: the packed data
    :rtype: str
    """
    l = len(data) + 1
    return struct.pack('Q', l) + data + '\n'


def unpack_data(data):
    """
    Generic data un-wrapper (see pack_data)

    Try to unpack data which was packed with pack_data.
    This returns the length data should have before a
    complete message has been formed and the message data
    as far as it can be unpacked (incomplete until
    len(data) is equal to the first return value).

    :param data: the data to try and unpack
    :type data: str
    :return: a tuple of required data length and current data
    :rtype: (int, str)
    """
    if len(data) < 8:
        return (len(data) + 1, data)
    l = struct.unpack('Q', data[:8])[0]
    return (l + 8, data[8:len(data)-1])


def unpack_complex(line):
    """
    Ease-of-use decorator of unpack_data()

    See unpack_data(), returns the portion of the line
    to prepend following data with and the portion which
    forms a complete message, or None.

    :param line: the incoming data to parse
    :type line: str
    :return: a tuple of data to buffer and data to forward
    :rtype: (str, str or None)
    """
    target, data = unpack_data(line)
    if target == len(line):
        # keep nothing, share data
        line = ""
        return line, data
    elif target < len(line):
        # keep past target-8, share up to target-8
        return line[target:], data[:target-9]
    return line, None


def fix_split(n, delimiter, args):
    """
    Fix a string split into n partitions

    Raw data sent over a line may contain delimiters used internally.
    Given that the amount of delimiters is known per message type,
    the data can be reconstructed for a given delimiter.

    :param n: the actual split count
    :type n: int
    :param delimiter: the delimited used to split the arguments
    :type delimiter: str
    :param args: the possibly superfluous arguments
    :type args: [str]
    :return: the args with length n
    :rtype: [str]
    """
    out = []
    if len(args) > n:
        for i in xrange(n):
            out.append(args[i] if i < n-1
                       else delimiter.join(args[i:]))
        return out
    else:
        return args
