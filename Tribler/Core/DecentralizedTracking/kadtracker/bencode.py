# Copyright (C) 2009 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

import cStringIO
from utils import log

class EncodeError(Exception):
    """Raised by encoder when invalid input"""
    
class DecodeError(Exception):
    """Raised by decoder when invalid bencode input"""
    
class RecursionDepthError(DecodeError):
    """Raised when the bencoded recursivity is too deep

    This check prevents us from using too much recursivity when an
    accidentally/maliciously constructed bencoded string looks like
    'llllllllllllllllllllllllllllllllllll' or
    'dddddddddddddddddddddddddddddddddddd'

    """
    pass

def encode(data):
    output = cStringIO.StringIO()
    try:
        encode_f[type(data)](data, output)
    except (KeyError):
        log.exception('Data: %s' % data)
        raise EncodeError, 'see ERROR log'
    result = output.getvalue()
    output.close()
    return result
        
def encode_str(data, output):
    """Encode a string object

    The result format is:
    <string length encoded in base ten ASCII>:<string data>

    """
    output.write('%d:%s' % (len(data), data))

def encode_int(data, output):
    """Encode an integer (or long) object

    The result format is:
    i<integer encoded in base ten ASCII>e
    
    """
    output.write('i%de' % data)

def encode_list(data, output):
    """Encode a list object

    The result format is:
    l<bencoded element>...<bencoded element>e

    """
    output.write('l')
    for item in data:
        encode_f[type(item)](item, output)
    output.write('e')

def encode_dict(data, output):
    """Encode a dict object

    The result format is:
    d<bencoded key><bencoded value>...<bencoded key><bencoded value>e 
    Keys must be string and will be encoded in lexicographical order

    """
    output.write('d')
    keys = data.keys()
    keys.sort()
    for key in keys:
        if type(key) != str: # key must be a string)
            raise EncodeError
        value = data[key]
        encode_f[str](key, output)
        encode_f[type(value)](value, output)
    output.write('e')


def decode(bencoded, max_depth=4):
    try:
        data, next_pos, = decode_f[bencoded[0]](bencoded, 0, max_depth)
    except (KeyError, IndexError, ValueError):
        raise DecodeError
    else:
        if next_pos != len(bencoded):
            raise DecodeError, 'Extra characters after valid bencode'
    return data
    

def decode_str(bencoded, pos, max_depth):
    """

    
    """
    colon_pos = bencoded.index(':', pos)
    str_len = int(bencoded[pos:colon_pos])
    next_pos = colon_pos + 1 + str_len
    return (bencoded[colon_pos+1:next_pos], next_pos)
        
def decode_int(bencoded, pos, max_depth):
    """

    
    """
    next_pos = bencoded.index('e', pos + 1) # skip 'i'
    return int(bencoded[pos+1:next_pos]), next_pos + 1 # correct for 'e'

def decode_list(bencoded, pos, max_depth):
    """

    
    """
    if max_depth == 0:
        raise RecursionDepthError, 'maximum recursion depth exceeded'
    
    result = []
    next_pos = pos + 1 # skip 'l'
    while bencoded[next_pos] != 'e':
        item, next_pos = decode_f[bencoded[next_pos]](bencoded,
                                                    next_pos, max_depth - 1)
        result.append(item)
    return result, next_pos + 1 # correct for 'e'

def decode_dict(bencoded, pos, max_depth):
    """
    
    """
    if max_depth == 0:
        raise RecursionDepthError, 'maximum recursion depth exceeded'
    
    result = {}
    next_pos = pos + 1 # skip 'd'
    while bencoded[next_pos] != 'e':
        key, next_pos = decode_f[bencoded[next_pos]](bencoded,
                                                   next_pos, max_depth - 1)
        value, next_pos = decode_f[bencoded[next_pos]](bencoded,
                                                       next_pos, max_depth - 1)
        result[key] = value
    return result, next_pos + 1 # skip 'e'


encode_f = {}
encode_f[str] = encode_str
encode_f[int] = encode_int
encode_f[long] = encode_int
encode_f[tuple] = encode_list
encode_f[list] = encode_list
encode_f[dict] = encode_dict

decode_f = {}
for i in xrange(10):
    decode_f[str(i)] = decode_str
decode_f['i'] = decode_int
decode_f['l'] = decode_list
decode_f['d'] = decode_dict


