#!/usr/bin/python

from datetime import datetime
from string import printable

class NotInterested(Exception):
    pass

def _counter(start):
    assert isinstance(start, (int, long))
    count = start
    while True:
        yield count
        count += 1

def _ignore_seperator(offset, stream):
    assert isinstance(offset, (int, long))
    assert isinstance(stream, str)
    for start in _counter(offset):
        if not stream[start] == " ":
            return start
    raise ValueError()

def _decode_str(offset, stream):
    assert isinstance(offset, (int, long))
    assert isinstance(stream, str)
    for split in _counter(offset):
        if stream[split] == ":":
            length = int(stream[offset:split])
            return split + length + 1, stream[split+1:split+length+1]
        elif not stream[split] in "1234567890":
            raise ValueError("Can not decode string length", stream[split])

def _decode_hex(offset, stream):
    assert isinstance(offset, (int, long))
    assert isinstance(stream, str)
    for split in _counter(offset):
        if stream[split] == ":":
            length = int(stream[offset:split])
            return split + length + 1, stream[split+1:split+length+1].decode("HEX")
        elif not stream[split] in "1234567890":
            raise ValueError("Can not decode string length", stream[split])

def _decode_unicode(offset, stream):
    assert isinstance(offset, (int, long))
    assert isinstance(stream, str)
    for split in _counter(offset):
        if stream[split] == ":":
            length = int(stream[offset:split])
            return split + length + 1, stream[split+1:split+length+1].decode("UTF8")
        elif not stream[split] in "1234567890":
            raise ValueError("Can not decode string length", stream[split])

def _decode_Hex(offset, stream):
    assert isinstance(offset, (int, long))
    assert isinstance(stream, str)
    for split in _counter(offset):
        if stream[split] == ":":
            length = int(stream[offset:split])
            return split + length + 1, stream[split+1:split+length+1].decode("HEX").decode("UTF8")
        elif not stream[split] in "1234567890":
            raise ValueError("Can not decode string length", stream[split])

def _decode_int(offset, stream):
    assert isinstance(offset, (int, long))
    assert isinstance(stream, str)
    for split in _counter(offset):
        if not stream[split] in "1234567890-":
            return split, int(stream[offset:split])

def _decode_float(offset, stream):
    assert isinstance(offset, (int, long))
    assert isinstance(stream, str)
    for split in _counter(offset):
        if not stream[split] in "1234567890-.e":
            return split, float(stream[offset:split])

def _decode_boolean(offset, stream):
    assert isinstance(offset, (int, long))
    assert isinstance(stream, str)
    if stream[offset:offset+4] == "True":
        return offset+4, True
    elif stream[offset:offset+5] == "False":
        return offset+5, False
    else:
        raise ValueError()

def _decode_none(offset, stream):
    assert isinstance(offset, (int, long))
    assert isinstance(stream, str)
    if stream[offset:offset+4] == "None":
        return offset+4, None
    else:
        raise ValueError("Expected None")

def _decode_tuple(offset, stream):
    assert isinstance(offset, (int, long))
    assert isinstance(stream, str)
    for split in _counter(offset):
        if stream[split] in ":":
            length = int(stream[offset:split])
            if not stream[split+1] == "(":
                raise ValueError("Expected '('", stream[split+1])
            offset = split + 2 # compensate for ':('
            l = []
            if length:
                for index in range(length):
                    offset, value = _decode(offset, stream)
                    l.append(value)

                    if index < length and stream[offset] == "," and stream[offset+1] == " ":
                        offset += 2 # compensate for ', '
                    elif index == length - 1 and stream[offset] == ")":
                        offset += 1 # compensate for ')'
                    else:
                        raise ValueError()
            else:
                if not stream[offset] == ")":
                    raise ValueError("Expected ')'", stream[split+1])
                offset += 1 # compensate for ')'

            return offset, tuple(l)

        elif not stream[split] in "1234567890":
            raise ValueError("Can not decode string length", stream[split])

def _decode_list(offset, stream):
    assert isinstance(offset, (int, long))
    assert isinstance(stream, str)
    for split in _counter(offset):
        if stream[split] in ":":
            length = int(stream[offset:split])
            if not stream[split+1] == "[":
                raise ValueError("Expected '['", stream[split+1])
            offset = split + 2 # compensate for ':['
            l = []
            if length:
                for index in range(length):
                    offset, value = _decode(offset, stream)
                    l.append(value)

                    if index < length and stream[offset] == "," and stream[offset+1] == " ":
                        offset += 2 # compensate for ', '
                    elif index == length - 1 and stream[offset] == "]":
                        offset += 1 # compensate for ']'
                    else:
                        raise ValueError()
            else:
                if not stream[offset] == "]":
                    raise ValueError("Expected ']'", stream[split+1])
                offset += 1 # compensate for ']'

            return offset, l

        elif not stream[split] in "1234567890":
            raise ValueError("Can not decode string length", stream[split])

def _decode_dict(offset, stream):
    assert isinstance(offset, (int, long))
    assert isinstance(stream, str)
    for split in _counter(offset):
        if stream[split] in ":":
            length = int(stream[offset:split])
            if not stream[split+1] == "{":
                raise ValueError("Expected '{'", stream[split+1])
            offset = split + 2 # compensate for ':{'
            d = {}
            for index in range(length):
                offset, key = _decode(offset, stream)
                if key in d:
                    raise ValueError("Duplicate map entry", key)
                if not stream[offset] == ":":
                    raise ValueError("Expected ':'", stream[offset])
                offset += 1 # compensate for ':'
                offset, value = _decode(offset, stream)
                d[key] = value

                if index < length and stream[offset] == "," and stream[offset+1] == " ":
                    offset += 2 # compensate for ', '
                elif index == length - 1 and stream[offset] == "}":
                    offset += 1 # compensate for '}'
                else:
                    raise ValueError()

            return offset, d

        elif not stream[split] in "1234567890":
            raise ValueError("Can not decode string length", stream[split])

def _decode(offset, stream):
    if stream[offset] in _decode_mapping:
        return _decode_mapping[stream[offset]](offset + 1, stream)
    else:
        raise ValueError("Can not decode {0}".format(stream[offset]))

def parse_line(stream, lineno=-1, interests=[]):
    assert isinstance(stream, str)
    assert isinstance(lineno, (int, long))
    assert isinstance(interests, (tuple, list, set))
    offset = _ignore_seperator(14, stream)
    if not stream[offset] == "s":
        raise ValueError("Expected a string encoded message")
    offset, message = _decode_str(offset+1, stream)

    if not interests or message in interests:
        stamp = datetime.strptime(stream[:14], "%Y%m%d%H%M%S")
        kargs = {}
        while offset < len(stream) - 1:
            offset = _ignore_seperator(offset, stream)
            for split in _counter(offset):
                if stream[split] == ":":
                    key = stream[offset:split].strip()
                    offset, value = _decode(split + 1, stream)
                    kargs[key] = value
                    break

                elif not stream[split] in _valid_key_chars:
                    raise ValueError("Can not decode character", stream[split], "on line", lineno)

        return lineno, stamp, message, kargs
    raise NotInterested(message)

def parse(filename, interests=[]):
    """
    Parse the content of FILENAME.

    Yields a (LINENO, DATETIME, MESSAGE, KARGS) tuple for each line in
    the file.
    """
    assert isinstance(filename, (str, unicode))
    assert isinstance(interests, (tuple, list, set))
    assert not filter(lambda x: not isinstance(x, str), interests)
    if isinstance(interests, (tuple, list)):
        interests = set(interests)
    for lineno, stream in zip(_counter(1), open(filename, "r")):
        if stream[0] == "#":
            continue
        try:
            yield parse_line(stream, lineno, interests)
        except NotInterested:
            pass

def parse_frequencies(filename, select=None):
    """
    Parse the content of FILENAME and calculate the frequenties of
    logged values.

    SELECT is an optional dictionary that tells the parser to only
    count specific keys from specific messages.  When SELECT is None,
    the frequenties of everything is calculated.  SELECT has the
    following structure:
    {msg.A : [key.A.1, key.A.2],
     msg.B : [key.B.1, key.B.2]}

    Yields a (LINENO, DATETIME, MESSAGE, KARGS, FREQUENTIES) tuple for
    each line in the file.

    Where FREQUENTIES has the following structure:
    { msg.A : [count.A, {key.A.1 : [count.A.1, {value.A.1.a : count.A.1.a}]}]}

    Note that print_frequencies(FREQUENTIES) can be used to display
    FREQUENTIES in a human readable way.
    """
    isinstance(select, dict)

    def parse_with_select():
        msg_freq = {}
        for message, keys in select.iteritems():
            key_freq = {}
            for key in keys:
                key_freq[key] = [0, {}]
            msg_freq[message] = [0, key_freq]

        for lineno, stamp, message, kargs in parse(filename):
            if message in msg_freq:
                msg_container = msg_freq[message]
                msg_container[0] += 1
                key_freq = msg_container[1]

                for key, value in kargs.iteritems():
                    if key in key_freq:
                        key_container = key_freq[key]
                        key_container[0] += 1
                        value_freq = key_container[1]
                        if isinstance(value, list):
                            for value in value:
                                value_freq[value] = value_freq.get(value, 0) + 1
                        else:
                            value_freq[value] = value_freq.get(value, 0) + 1

            yield lineno, stamp, message, kargs, msg_freq

    def parse_without_select():
        msg_freq = {}
        for lineno, stamp, message, kargs in parse(filename):
            if not message in msg_freq:
                msg_freq[message] = [0, {}]

            msg_container = msg_freq[message]
            msg_container[0] += 1
            key_freq = msg_container[1]

            for key, value in kargs.iteritems():
                if not key in key_freq:
                    key_freq[key] = [0, {}]

                key_container = key_freq[key]
                key_container[0] += 1
                value_freq = key_container[1]
                if isinstance(value, list):
                    for value in value:
                        value_freq[value] = value_freq.get(value, 0) + 1
                else:
                    value_freq[value] = value_freq.get(value, 0) + 1

            yield lineno, stamp, message, kargs, msg_freq

    if select:
        return parse_with_select()
    else:
        return parse_without_select()

def print_frequencies(frequencies, merge=None, limit=8):
    def print_helper(freq, total):
        for count, value in sorted([(count, value) for value, count in freq.iteritems()], reverse=True)[:limit]:
            if isinstance(value, str):
                for char in value:
                    if not char in printable:
                        print "{0:5} {1:4.0%}:  {2}".format(count, 1.0*count/total, value.encode("HEX"))
                        break
                else:
                    print "{0:5} {1:4.0%}:  {2}".format(count, 1.0*count/total, value)
            else:
                print "{0:5} {1:4.0%}:  {2}".format(count, 1.0*count/total, value)

    def print_with_merge():
        freq = {}
        for title, selection in merge.iteritems():
            count = 0
            for message, key in selection:
                if message in frequencies:
                    key_freq = frequencies[message][1]
                    if key in key_freq:
                        key_container = key_freq[key]
                        count += key_container[0]
                        for value, count in key_container[1].iteritems():
                            freq[value] = freq.get(value, 0) + count

            print "+++ {0} . {1} +++".format(title, count)
            print_helper(freq, count)
            print

    def print_without_merge():
        for message, (msg_count, key_freq) in frequencies.iteritems():
            print ">>>>> {0:20}   {1:5}      <<<<<".format(message, msg_count)
            for key, (key_count, value_freq) in key_freq.iteritems():
                print ">     {0:20}   {1:5} {2:4.0%}     <".format(key, key_count, 1.0*key_count/msg_count)
                print_helper(value_freq, key_count)
            print

    if merge:
        print_with_merge()
    else:
        print_without_merge()

_valid_key_chars = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ1234567890_"
_decode_mapping = {"s":_decode_str,
                   "h":_decode_hex,
                   "u":_decode_unicode,
                   "H":_decode_Hex,
                   "i":_decode_int,
                   "f":_decode_float,
                   "b":_decode_boolean,
                   "n":_decode_none,
                   "t":_decode_tuple,
                   "l":_decode_list,
                   "m":_decode_dict}
