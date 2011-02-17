def _a_encode_int(value, mapping):
    """
    42 --> ('2', 'i', '42')
    """
    assert isinstance(value, int), "VALUE has invalid type: %s" % type(value)
    value = str(value).encode("UTF-8")
    return (str(len(value)).encode("UTF-8"), "i", value)

def _a_encode_float(value, mapping):
    """
    4.2 --> ('3', 'f', '4.2')
    """
    assert isinstance(value, float), "VALUE has invalid type: %s" % type(value)
    value = str(value).encode("UTF-8")
    return (str(len(value)).encode("UTF-8"), "f", value)

def _a_encode_unicode(value, mapping):
    """
    'foo-bar' --> ('7', 's', 'foo-bar')
    """
    assert isinstance(value, unicode), "VALUE has invalid type: %s" % type(value)
    value = value.encode("UTF-8")
    return (str(len(value)).encode("UTF-8"), "s", value)

def _a_encode_bytes(value, mapping):
    """
    'foo-bar' --> ('7', 'b', 'foo-bar')
    """
    assert isinstance(value, bytes), "VALUE has invalid type: %s" % type(value)
    return (str(len(value)).encode("UTF-8"), "b", value)

def _a_encode_iterable(values, mapping):
    """
    [1,2,3] --> ['3', 't', '1', 'i', '1', '1', 'i', '2', '1', 'i', '3']
    (1,2) --> ['2', 't', '1', 'i', '1', '1', 'i', '2']
    """
    assert isinstance(values, list) or isinstance(values, tuple), "VALUE has invalid type: %s" % type(value)
    encoded = [str(len(values)).encode("UTF-8"), "t"]
    extend = encoded.extend
    for value in values:
        extend(mapping[type(value)](value, mapping))
    return encoded

def _a_encode_dictionary(values, mapping):
    """
    {'foo':'bar', 'moo':'milk'} --> ['2', 'd', '3', 's', 'foo', '3', 's', 'bar', '3', 's', 'moo', '4', 's', 'milk']
    """
    assert isinstance(values, dict), "VALUE has invalid type: %s" % type(value)
    encoded = [str(len(values)).encode("UTF-8"), "d"]
    extend = encoded.extend
    for key, value in sorted(values.items()):
        assert type(key) in mapping, (key, values)
        assert type(value) in mapping, (value, values)
        extend(mapping[type(key)](key, mapping))
        extend(mapping[type(value)](value, mapping))
    return encoded

_a_encode_mapping = {int:_a_encode_int,
                     float:_a_encode_float,
                     unicode:_a_encode_unicode,
                     str:_a_encode_bytes,
                     list:_a_encode_iterable,
                     tuple:_a_encode_iterable,
                     dict:_a_encode_dictionary}

def encode(data):
    """
    Encode DATA into version 'a' binary stream.

    DATA can be any: int, float, string, unicode, list, tuple, or
    dictionary.

    Lists are considered to be tuples.  I.e. when decoding an
    encoded list it will come out as a tuple.

    The encoding process is done using version 'a' which is
    indicated by the first byte of the resulting binary stream.
    """
    return "a" + "".join(_a_encode_mapping[type(data)](data, _a_encode_mapping))

def _a_decode_int(stream, offset, count, _):
    """
    '2i42',2,2 --> 4,42
    """
    return offset+count, int(stream[offset:offset+count])

def _a_decode_float(stream, offset, count, _):
    """
    '3f4.2',2,3 --> 5,4.2
    """
    return offset+count, float(stream[offset:offset+count])

def _a_decode_unicode(stream, offset, count, _):
    """
    '7sfoo-bar',2,7 --> 9,u'foo-bar'
    """
    if len(stream) >= offset+count:
        return offset+count, stream[offset:offset+count].decode("UTF-8")
    else:
        raise ValueError("Invalid stream length", len(stream), offset + count)

def _a_decode_bytes(stream, offset, count, _):
    """
    '7bfoo-bar',2,7 --> 9,'foo-bar'
    """
    if len(stream) >= offset+count:
        return offset+count, stream[offset:offset+count]
    else:
        raise ValueError("Invalid stream length", len(stream), offset + count)

def _a_decode_iterable(stream, offset, count, mapping):
    """
    '3l1i11i21i3',2,3 --> 11,[1,2,3]
    '2t1i11i2',2,2 --> 8,[1,2]
    """
    container = []
    for _ in range(count):

        index = offset
        while 48 <= ord(stream[index]) <= 57:
            index += 1
        # print
        # print offset, index
        # print stream[:100]
        # print stream[offset:100]
        # print
        offset, value = mapping[stream[index]](stream, index+1, int(stream[offset:index]), mapping)
        container.append(value)

    return offset, tuple(container)

def _a_decode_dictionary(stream, offset, count, mapping):
    """
    '2d3sfoo3sbar3smoo4smilk',2,2 -> 23,{'foo':'bar', 'moo':'milk'}
    """
    container = {}
    for _ in range(count):

        index = offset
        while 48 <= ord(stream[index]) <= 57:
            index += 1
        offset, key = mapping[stream[index]](stream, index+1, int(stream[offset:index]), mapping)

        index = offset
        while 48 <= ord(stream[index]) <= 57:
            index += 1
        offset, value = mapping[stream[index]](stream, index+1, int(stream[offset:index]), mapping)

        container[key] = value

    if len(container) < count:
        raise ValueError("Duplicate key in dictionary")
    return offset, container

_a_decode_mapping = {"i":_a_decode_int,
                     "f":_a_decode_float,
                     "s":_a_decode_unicode,
                     "b":_a_decode_bytes,
                     "t":_a_decode_iterable,
                     "d":_a_decode_dictionary}

def decode(stream, offset=0):
    """
    Decode STREAM from index OFFSET and further into a python data
    structure.

    Only version 'a' decoding is supported.  This version is
    indicated by the first byte in the binary STREAM.
    """
    assert isinstance(stream, bytes), "STREAM has invalid type: %s" % type(stream)
    assert isinstance(offset, int), "OFFSET has invalid type: %s" % type(offset)
    if stream[offset] == "a":
        index = offset + 1
        while 48 <= ord(stream[index]) <= 57:
            index += 1
        return _a_decode_mapping[stream[index]](stream, index+1, int(stream[offset+1:index]), _a_decode_mapping)

    raise ValueError("Unknown version found")

