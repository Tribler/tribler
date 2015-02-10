import logging

logger = logging.getLogger(__name__)


def _a_encode_int(value, mapping):
    """
    42 --> ('2', 'i', '42')
    """
    assert isinstance(value, int), "VALUE has invalid type: %s" % type(value)
    value = str(value).encode("UTF-8")
    return str(len(value)).encode("UTF-8"), "i", value


def _a_encode_long(value, mapping):
    """
    42 --> ('2', 'J', '42')
    """
    assert isinstance(value, long), "VALUE has invalid type: %s" % type(value)
    value = str(value).encode("UTF-8")
    return str(len(value)).encode("UTF-8"), "J", value


def _a_encode_float(value, mapping):
    """
    4.2 --> ('3', 'f', '4.2')
    """
    assert isinstance(value, float), "VALUE has invalid type: %s" % type(value)
    value = str(value).encode("UTF-8")
    return str(len(value)).encode("UTF-8"), "f", value


def _a_encode_unicode(value, mapping):
    """
    'foo-bar' --> ('7', 's', 'foo-bar')
    """
    assert isinstance(value, unicode), "VALUE has invalid type: %s" % type(value)
    value = value.encode("UTF-8")
    return str(len(value)).encode("UTF-8"), "s", value


def _a_encode_bytes(value, mapping):
    """
    'foo-bar' --> ('7', 'b', 'foo-bar')
    """
    assert isinstance(value, bytes), "VALUE has invalid type: %s" % type(value)
    return str(len(value)).encode("UTF-8"), "b", value


def _a_encode_list(values, mapping):
    """
    [1,2,3] --> ['3', 'l', '1', 'i', '1', '1', 'i', '2', '1', 'i', '3']
    """
    assert isinstance(values, list), "VALUE has invalid type: %s" % type(values)
    encoded = [str(len(values)).encode("UTF-8"), "l"]
    extend = encoded.extend
    for value in values:
        extend(mapping[type(value)](value, mapping))
    return encoded


def _a_encode_set(values, mapping):
    """
    [1,2,3] --> ['3', 'l', '1', 'i', '1', '1', 'i', '2', '1', 'i', '3']
    """
    assert isinstance(values, set), "VALUE has invalid type: %s" % type(values)
    encoded = [str(len(values)).encode("UTF-8"), "L"]
    extend = encoded.extend
    for value in values:
        extend(mapping[type(value)](value, mapping))
    return encoded


def _a_encode_tuple(values, mapping):
    """
    (1,2) --> ['2', 't', '1', 'i', '1', '1', 'i', '2']
    """
    assert isinstance(values, tuple), "VALUE has invalid type: %s" % type(values)
    encoded = [str(len(values)).encode("UTF-8"), "t"]
    extend = encoded.extend
    for value in values:
        extend(mapping[type(value)](value, mapping))
    return encoded


def _a_encode_dictionary(values, mapping):
    """
    {'foo':'bar', 'moo':'milk'} --> ['2', 'd', '3', 's', 'foo', '3', 's', 'bar', '3', 's', 'moo', '4', 's', 'milk']
    """
    assert isinstance(values, dict), "VALUE has invalid type: %s" % type(values)
    encoded = [str(len(values)).encode("UTF-8"), "d"]
    extend = encoded.extend
    for key, value in sorted(values.items()):
        assert type(key) in mapping, (key, values)
        assert type(value) in mapping, (value, values)
        extend(mapping[type(key)](key, mapping))
        extend(mapping[type(value)](value, mapping))
    return encoded


def _a_encode_none(value, mapping):
    """
    None --> ['0', 'n']
    """
    return ['0n']


def _a_encode_bool(value, mapping):
    """
    True  --> ['0', 'T']
    False --> ['0', 'F']
    """
    return ['0T' if value else '0F']

_a_encode_mapping = {int: _a_encode_int,
                     long: _a_encode_long,
                     float: _a_encode_float,
                     unicode: _a_encode_unicode,
                     str: _a_encode_bytes,
                     list: _a_encode_list,
                     set: _a_encode_set,
                     tuple: _a_encode_tuple,
                     dict: _a_encode_dictionary,
                     type(None): _a_encode_none,
                     bool: _a_encode_bool}

# def _b_uint_to_bytes(i):
#     assert isinstance(i, (int, long))
#     assert i >= 0
#     if i == 0:
#         return "\x00"

#     else:
#         bit8 = 16*8
#         mask8 = 2**8-1
#         mask7 = 2**7-1
#         l = []
#         while i:
#             l.append(bit8 | mask7 & i)
#             i >>= 7
#         l[0] &= mask7
#         return "".join(chr(k) for k in reversed(l))

# from math import log
# from struct import pack

# def _b_encode_int(value, mapping):
#     """
#     42 --> (_b_uint_to_bytes(2), 'i', struct.pack('>h', 42))
#     """
#     assert isinstance(value, (int, long)), "VALUE has invalid type: %s" % type(value)
#     length = 2 if value == 0 else int(log(value, 2) / 8) + 1
#     return (_b_uint_to_bytes(length), "i", pack({1:">h", 2:">h", 3:">i", 4:">i", 5:">l", 6:">l", 7:">l", 8:">l"}.get(length, ">q"), value))

# def _b_encode_float(value, mapping):
#     """
#     4.2 --> (_b_uint_to_bytes(4), 'f', struct.pack('>f', 4.2))
#     """
#     assert isinstance(value, float), "VALUE has invalid type: %s" % type(value)
#     return (_b_uint_to_bytes(4), "f", pack(">f", value))

# def _b_encode_unicode(value, mapping):
#     """
#     'foo-bar' --> (_b_uint_to_bytes(7), 's', 'foo-bar')
#     """
#     assert isinstance(value, unicode), "VALUE has invalid type: %s" % type(value)
#     value = value.encode("UTF-8")
#     return ("s", _b_uint_to_bytes(len(value)), value)

# def _b_encode_bytes(value, mapping):
#     """
#     'foo-bar' --> (_b_uint_to_bytes(7), 'b', 'foo-bar')
#     """
#     assert isinstance(value, bytes), "VALUE has invalid type: %s" % type(value)
#     return (_b_uint_to_bytes(len(value)), "b", value)

# def _b_encode_list(values, mapping):
#     """
#     [1,2,3] --> [_b_uint_to_bytes(3), 'l'] + _b_encode_int(1) + _b_encode_int(2) + _b_encode_int(3)
#     """
#     assert isinstance(values, list), "VALUE has invalid type: %s" % type(value)
#     encoded = [_b_uint_to_bytes(len(values)), "l"]
#     extend = encoded.extend
#     for value in values:
#         extend(mapping[type(value)](value, mapping))
#     return encoded

# def _b_encode_tuple(values, mapping):
#     """
#     (1,2) --> [_b_uint_to_bytes(3), 't'] + _b_encode_int(1) + _b_encode_int(2)
#     """
#     assert isinstance(values, tuple), "VALUE has invalid type: %s" % type(value)
#     encoded = [_b_uint_to_bytes(len(values)), "t"]
#     extend = encoded.extend
#     for value in values:
#         extend(mapping[type(value)](value, mapping))
#     return encoded

# def _b_encode_dictionary(values, mapping):
#     """
#     {'foo':'bar', 'moo':'milk'} --> [_b_uint_to_bytes(2), 'd'] + _b_encode_bytes('foo') + _b_encode_bytes('bar') + _b_encode_bytes('moo') +_b_encode_bytes('milk')
#     """
#     assert isinstance(values, dict), "VALUE has invalid type: %s" % type(value)
#     encoded = [_b_uint_to_bytes(len(values)), "d"]
#     extend = encoded.extend
#     for key, value in sorted(values.items()):
#         assert type(key) in mapping, (key, values)
#         assert type(value) in mapping, (value, values)
#         extend(mapping[type(key)](key, mapping))
#         extend(mapping[type(value)](value, mapping))
#     return encoded

# def _b_encode_none(value, mapping):
#     """
#     None --> [_b_uint_to_bytes(0), 'n']
#     """
#     return [_b_uint_to_bytes(0), "n"]

# def _b_encode_bool(value, mapping):
#     """
#     True  --> [_b_uint_to_bytes(0), 'T']
#     False --> [_b_uint_to_bytes(0), 'F']
#     """
#     return [_b_uint_to_bytes(0), "T" if value else "F"]

# _b_encode_mapping = {int:_b_encode_int,
#                      long:_b_encode_int,
#                      float:_b_encode_float,
#                      unicode:_b_encode_unicode,
#                      str:_b_encode_bytes,
#                      list:_b_encode_list,
#                      tuple:_b_encode_tuple,
#                      dict:_b_encode_dictionary,
#                      type(None):_b_encode_none,
#                      bool:_b_encode_bool}


def bytes_to_uint(stream, offset=0):
    assert isinstance(stream, str)
    assert isinstance(offset, (int, long))
    assert offset >= 0
    bit8 = 16 * 8
    mask7 = 2 ** 7 - 1
    i = 0
    while offset < len(stream):
        c = ord(stream[offset])
        i |= mask7 & c
        if not bit8 & c:
            return i
        offset += 1
        i <<= 7
    raise ValueError()


def encode(data, version="a"):
    """
    Encode DATA into version 'a' binary stream.

    DATA can be any: int, float, string, unicode, list, tuple, or
    dictionary.

    Lists are considered to be tuples.  I.e. when decoding an
    encoded list it will come out as a tuple.

    The encoding process is done using version 'a' which is
    indicated by the first byte of the resulting binary stream.
    """
    assert isinstance(version, str)
    if version == "a":
        return "a" + "".join(_a_encode_mapping[type(data)](data, _a_encode_mapping))
    elif version == "b":
        # raise ValueError("This version is not yet implemented")
        return "b" + "".join(_b_encode_mapping[type(data)](data, _b_encode_mapping))
    else:
        raise ValueError("Unknown encode version")


def _a_decode_int(stream, offset, count, _):
    """
    'a2i42',3,2 --> 5,42
    """
    return offset + count, int(stream[offset:offset + count])


def _a_decode_long(stream, offset, count, _):
    """
    'a2J42',3,2 --> 5,42
    """
    return offset + count, long(stream[offset:offset + count])


def _a_decode_float(stream, offset, count, _):
    """
    'a3f4.2',3,3 --> 6,4.2
    """
    return offset + count, float(stream[offset:offset + count])


def _a_decode_unicode(stream, offset, count, _):
    """
    'a3sbar',3,3 --> 6,u'bar'
    """
    if len(stream) >= offset + count:
        return offset + count, stream[offset:offset + count].decode("UTF-8")
    else:
        raise ValueError("Invalid stream length", len(stream), offset + count)


def _a_decode_bytes(stream, offset, count, _):
    """
    'a3bfoo',3,3 --> 6,'foo'
    """
    if len(stream) >= offset + count:
        return offset + count, stream[offset:offset + count]
    else:
        raise ValueError("Invalid stream length", len(stream), offset + count)


def _a_decode_list(stream, offset, count, mapping):
    """
    'a1l3i123',3,1 --> 8,[123]
    'a2l1i41i2',3,1 --> 8,[4,2]
    """
    container = []
    for _ in range(count):

        index = offset
        while 48 <= ord(stream[index]) <= 57:
            index += 1
        offset, value = mapping[stream[index]](stream, index + 1, int(stream[offset:index]), mapping)
        container.append(value)

    return offset, container


def _a_decode_set(stream, offset, count, mapping):
    """
    'a1L3i123',3,1 --> 8,set(123)
    'a2L1i41i2',3,1 --> 8,set(4,2)
    """
    container = set()
    for _ in range(count):

        index = offset
        while 48 <= ord(stream[index]) <= 57:
            index += 1
        offset, value = mapping[stream[index]](stream, index + 1, int(stream[offset:index]), mapping)
        container.add(value)

    return offset, container


def _a_decode_tuple(stream, offset, count, mapping):
    """
    'a1t3i123',3,1 --> 8,[123]
    'a2t1i41i2',3,1 --> 8,[4,2]
    """
    container = []
    for _ in range(count):

        index = offset
        while 48 <= ord(stream[index]) <= 57:
            index += 1
        offset, value = mapping[stream[index]](stream, index + 1, int(stream[offset:index]), mapping)
        container.append(value)

    return offset, tuple(container)


def _a_decode_dictionary(stream, offset, count, mapping):
    """
    'a2d3sfoo3sbar3smoo4smilk',3,2 -> 24,{'foo':'bar', 'moo':'milk'}
    """
    container = {}
    for _ in range(count):

        index = offset
        while 48 <= ord(stream[index]) <= 57:
            index += 1
        offset, key = mapping[stream[index]](stream, index + 1, int(stream[offset:index]), mapping)

        index = offset
        while 48 <= ord(stream[index]) <= 57:
            index += 1
        offset, value = mapping[stream[index]](stream, index + 1, int(stream[offset:index]), mapping)

        container[key] = value

    if len(container) < count:
        raise ValueError("Duplicate key in dictionary")
    return offset, container


def _a_decode_none(stream, offset, count, mapping):
    """
    'a0n',3,0 -> 3,None
    """
    assert count == 0
    return offset, None


def _a_decode_true(stream, offset, count, mapping):
    """
    'a0T',3,1 -> 3,True
    """
    assert count == 0
    return offset, True


def _a_decode_false(stream, offset, count, mapping):
    """
    'a0F',3,1 -> 3,False
    """
    assert count == 0
    return offset, False

_a_decode_mapping = {"i": _a_decode_int,
                     "J": _a_decode_long,
                     "f": _a_decode_float,
                     "s": _a_decode_unicode,
                     "b": _a_decode_bytes,
                     "l": _a_decode_list,
                     "L": _a_decode_set,
                     "t": _a_decode_tuple,
                     "d": _a_decode_dictionary,
                     "n": _a_decode_none,
                     "T": _a_decode_true,
                     "F": _a_decode_false}


def decode(stream, offset=0):
    """
    Decode STREAM from index OFFSET and further into a python data
    structure.

    Returns the new OFFSET of the stream and the decoded data.

    Only version 'a' decoding is supported.  This version is
    indicated by the first byte in the binary STREAM.
    """
    assert isinstance(stream, bytes), "STREAM has invalid type: %s" % type(stream)
    assert isinstance(offset, int), "OFFSET has invalid type: %s" % type(offset)
    if stream[offset] == "a":
        index = offset + 1
        while 48 <= ord(stream[index]) <= 57:
            index += 1
        return _a_decode_mapping[stream[index]](stream, index + 1, int(stream[offset + 1:index]), _a_decode_mapping)

    raise ValueError("Unknown version found")

if __debug__:
    if __name__ == "__main__":
        # def uint_to_bytes(i):
        #     assert isinstance(i, (int, long))
        #     assert i >= 0
        #     if i == 0:
        #         return "\x00"

        #     else:
        #         bit8 = 16*8
        #         mask8 = 2**8-1
        #         mask7 = 2**7-1
        #         l = []
        #         while i:
        #             l.append(bit8 | mask7 & i)
        #             i >>= 7
        #         l[0] &= mask7
        #         return "".join(chr(k) for k in reversed(l))

        # def bytes_to_uint(stream, offset=0):
        #     assert isinstance(stream, str)
        #     assert isinstance(offset, (int, long))
        #     assert offset >= 0
        #     bit8 = 16*8
        #     mask7 = 2**7-1
        #     i = 0
        #     while offset < len(stream):
        #         c = ord(stream[offset])
        #         i |= mask7 & c
        #         if not bit8 & c:
        #             return i
        #         offset += 1
        #         i <<= 7
        #     raise ValueError()

        # def test(i):
        #     s = uint_to_bytes(i)
        #     print "%5d %15s %8s" % (i, bin(i), s.encode("HEX")), [bin(ord(x)) for x in s]
        #     j = bytes_to_uint(s + "kjdhsakdjhkjhsdasa")
        #     assert i == j, (i, j)
        #     return s

        # test(int("10110101010", 2))
        # for i in xrange(-10, 1024*150):
        #     if len(test(i)) > 2:
        #         break
        # exit(0)

        from Tribler.Core.BitTornado.bencode import bencode, bdecode

        def test(in_, verbose=True):
            value = in_
            s = encode(value)
            length, v = decode(s)
            if verbose:
                logger.info("dispersy A %s : %s -> %s", length, value, s)
            else:
                logger.info("dispersy A %s", length)
            assert len(s) == length, (len(s), length)
            assert value == v, (value, v)

            # value = in_
            # s = encode(value, "b")
            # length = len(s)
            # length, v = decode(s)
            # if verbose:
            #     print "dispersy B", length, ":", value, "->", s
            # else:
            #     print "dispersy B", length
            # assert len(s) == length, (len(s), length)
            # assert value == v, (value, v)

            value = in_
            if isinstance(value, (float, type(None), set)):
                logger.info("bittorrent not supported")
            else:
                # exception: tuple types are encoded as list
                if isinstance(value, tuple):
                    value = list(value)

                # exception: dictionary types may only have string for keys
                if isinstance(value, dict):
                    convert = lambda a: str(a) if not isinstance(a, (str, unicode)) else a
                    value = dict((convert(a), b) for a, b in value.iteritems())

                s = bencode(value)
                v = bdecode(s)

                if verbose:
                    logger.info("bittorrent %d : %s -> %s", len(s), value, s)
                else:
                    logger.info("bittorrent %d", len(s))
                assert value == v, (value, v)

        test(4242)
        test(42)
        test(42)
        test(4.2)
        test(0.0000000000000000042)
        test("foo")
        test(u"bar")
        test([123])
        test([4, 2])
        test((4, 2))
        test({'foo': 'bar', 'moo': 'milk'})
        test({u'foo': 'bar'})
        test({4: 2})
        test(None)
        test(range(1000), False)
        test(["F" * 20 for _ in range(1000)], False)
        test(set(['a', 'b']))
        test(True)
        test(False)
        test([True, True, False, True, False, False])
