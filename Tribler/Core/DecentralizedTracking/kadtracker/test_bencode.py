# Copyright (C) 2009 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

from nose.tools import assert_raises, raises

import cStringIO

from utils import log

from bencode import *


test_data = [
    # strings
    ('a', '1:a'),
    ('1', '1:1'),
    ('0123456789abcdef', '16:0123456789abcdef'),
    ('A' * 100, '100:' + 'A' * 100),
    ('{', '1:{'),
    ('[', '1:['),
    (chr(2), '1:' + chr(2)),
    # integers
    (0, 'i0e'),
    (000, 'i0e'),
    (1234567890, 'i1234567890e'),
    (-1, 'i-1e'),
    # lists
    ([], 'le'),
    ([[[[]]]], 'lllleeee'), # maximum recursivity depht
    ([1, 2, 3], 'li1ei2ei3ee'),
    (['A', 'B', 'C'], 'l1:A1:B1:Ce'),
    (['A', 2, 'C'], 'l1:Ai2e1:Ce'),
    ([1, ['X'], 2, 'Z'], 'li1el1:Xei2e1:Ze'),
    # dictionaries
    ({}, 'de'),
    ({'key': 'a'}, 'd3:key1:ae'),
    ({'ZZZ': 12345}, 'd3:ZZZi12345ee'),
    # ordered dictionaries
    ({'a':{'A':1, 'C':2, 'B':3}, 'b':2, 'z':3, 'c':[]},
     'd1:ad1:Ai1e1:Bi3e1:Ci2ee1:bi2e1:cle1:zi3ee'),
    # mixed types
    ({'A': [], 'B': {'B': [1], 'C': [], 'D':{}}, 'C': 9},
     'd1:Ale1:Bd1:Bli1ee1:Cle1:Ddee1:Ci9ee'),
    ]

test_data_encode_error = [
    (False, EncodeError),
    # Using no-string types in dict
    ({1:1}, EncodeError),
    ({None:1}, EncodeError),
    ({(1,2):1}, EncodeError),
#    ({1: {1: {1: {1: {}}}}}, RecursionDepthError), no recursion limit encoding
    ]

test_data_decode_error = [
    ('', DecodeError), # empty bencode
    ('leEXTRA', DecodeError), # extra characters after bencode
    ('xWHATEVER', DecodeError), # start with invalid character
    ('dxe', DecodeError), # invalid special character
    ('ixe', DecodeError), # invalid integer 
    ('li2e', DecodeError), # list end missing
    ('li2eee', DecodeError), # extra end
    ('d3:KEYe', DecodeError), # value missing
    ('lllll', RecursionDepthError),
    ('ddddd', RecursionDepthError),
    ]


def debug_print(test_num, input_, expected, output):
    log.debug('test_num: %d' % test_num)
    log.debug('input:    %s' % input_)
    log.debug('expected: %s' % expected)
    log.debug('output:   %s' % output)
       

class TestEncode():

    def setup(self):
        pass
#        log.critical('************* BEGIN **************')

    def test_encode(self):
        for i, (data, expected) in enumerate(test_data):
            bencoded = None
            try:
                bencoded = encode(data)
            except(Exception), e:
                debug_print(i, data, expected, e)
                raise
            if bencoded != expected:
                debug_print(i, data, expected, bencoded)
                assert False


    def test_encode_error(self):
        for i, (data, expected) in enumerate(test_data_encode_error):
            try:
                encode(data)
            except expected:
                log.error(
                    "**IGNORE ERROR LOG** This exception was raised by a test")
            except (Exception), e:
                debug_print(i, data, expected, e)
                raise
            else:
                debug_print(i, data, expected, 'NO EXCEPTION RAISED')
                assert False
#            assert_raises(expected, encode_list, data, output)
       
class TestDecode:

    def setup(self):
        pass
#        log.critical('************* BEGIN **************')

    def test_decode(self):
        for i, (expected, bencoded) in enumerate(test_data):
            data = None
            try:
                data = decode(bencoded)
            except (Exception), e:
                debug_print(i, bencoded, expected, e)
                #raise
            else:
                if data != expected:
                    debug_print(i, bencoded, expected, data)
                    assert False

    def test_decode_error(self):
        for i, (bencoded, expected) in enumerate(test_data_decode_error):
            try:
                decode(bencoded)
            except expected:
                pass
            except (Exception), e:
                debug_print(i, bencoded, expected, e)
                raise
            else:
                debug_print(i, bencoded, expected, 'NO EXCEPTION RAISED')
                assert False
#            assert_raises(expected, decode, data)

            
