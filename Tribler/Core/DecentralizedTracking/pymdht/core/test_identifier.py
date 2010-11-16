# Released under GNU LGPL 2.1
# Copyright (C) 2009-2010 Raul Jimenez
# See LICENSE.txt for more information

import random

import logging, logging_conf

from nose.tools import eq_, ok_, assert_raises, raises
import test_const as tc

import identifier
from identifier import Id, RandomId, IdError
from identifier import ID_SIZE_BYTES, ID_SIZE_BITS, BITS_PER_BYTE

logging_conf.testing_setup(__name__)
logger = logging.getLogger('dht')


BIN_ID0 = '\x00' * ID_SIZE_BYTES
BIN_ID1 = '\x01' * ID_SIZE_BYTES
BIN_ID2 = '\x02' * ID_SIZE_BYTES
DIST0_1 = '\x01' * ID_SIZE_BYTES
DIST1_2 = '\x03' * ID_SIZE_BYTES

HEX_ID1 =  '01' * ID_SIZE_BYTES


class TestId(object):
    
    def test_create(self):
        _ = Id(BIN_ID1)
        _ = RandomId()
        assert_raises(IdError, Id, 1)
        assert_raises(IdError, Id, '1')
        _ = Id('1' * 40) # Hexadecimal
        assert_raises(IdError, Id, 'Z'*40)
        eq_(Id('\x00'*20).bin_id, Id('0'*40).bin_id)
        eq_(Id('\xff'*20), Id('f'*40))

    def test_has_repr(self):
        eq_(repr(Id(BIN_ID1)), '01' * ID_SIZE_BYTES)
        
    def test_is_hashable(self):
        d = {Id(BIN_ID1): 1}
        
    def test_util(self):
        assert identifier._bin_to_hex(BIN_ID1) == HEX_ID1
        assert identifier._byte_xor('\0', '\1') == '\1'
    
    def test_first_different_byte(self):
        str1 = '0' * ID_SIZE_BYTES
        for i in range(ID_SIZE_BYTES):
            str2 = '0' * i + '1' * (ID_SIZE_BYTES - i)
            logger.debug('test_num: %d, _first_different_byte: %d' % (
                i, identifier._first_different_byte(str1, str2)))
            assert identifier._first_different_byte(str1, str2) == i
        assert_raises(IndexError,
                      identifier._first_different_byte, str1, str1)

    def test_first_different_bit(self):
        assert identifier._first_different_bit('\0', '\x01') == 7
        assert identifier._first_different_bit('\0', '\x02') == 6
        assert identifier._first_different_bit('\0', '\x04') == 5
        assert identifier._first_different_bit('\0', '\x09') == 4
        assert identifier._first_different_bit('\0', '\x10') == 3
        assert identifier._first_different_bit('\0', '\x23') == 2
        assert identifier._first_different_bit('\0', '\x40') == 1
        assert identifier._first_different_bit('\0', '\xa5') == 0
        assert identifier._first_different_bit('\0', '\xff') == 0
        assert_raises(AssertionError, identifier._first_different_bit,
                      '\5', '\5')

    def test_bin_id(self):
        assert Id(BIN_ID1).bin_id == BIN_ID1

    def test_equal(self):
        id1 = Id(BIN_ID0)
        assert id1 == id1 # same instance
        assert id1 == Id(BIN_ID0) #different instance, same value
        assert id1 != Id(BIN_ID1)


    @raises(AttributeError)
    def test_bin_id_read_only(self):
        id1 = Id(BIN_ID1)
        id1.bin_id = BIN_ID2

    def test_str(self):
        id1 = Id(BIN_ID1)
        assert BIN_ID1 == '%s' % id1

    def test_distance(self):
        id1 = Id(BIN_ID1)
        id2 = Id(BIN_ID2)
        dist1_2 = Id(DIST1_2)
        assert id1.distance(id2).bin_id == dist1_2.bin_id
        assert id2.distance(id1).bin_id == dist1_2.bin_id 
        #assert id1.distance(id1).bin_id == ZeroId().bin_id

    def test_log_distance(self):
        id0 = Id(BIN_ID0)
        id1 = Id(BIN_ID1)
        id2 = Id(BIN_ID2)
        eq_(id0.log_distance(id0), -1)
        eq_(id0.log_distance(id1), ID_SIZE_BITS - 8)
        eq_(id0.log_distance(id2), ID_SIZE_BITS - 7)

        id_log = (
            (Id('\x00' + '\xff' * (ID_SIZE_BYTES - 1)),
             BITS_PER_BYTE * (ID_SIZE_BYTES - 1) - 1),
            
            (Id('\x53' * ID_SIZE_BYTES),
            BITS_PER_BYTE * ID_SIZE_BYTES - 2),
            
            (Id(BIN_ID0[:7] + '\xff' * (ID_SIZE_BYTES - 7)),
             (ID_SIZE_BYTES - 7) * BITS_PER_BYTE - 1),
            
            (Id(BIN_ID0[:9] + '\x01' * (ID_SIZE_BYTES - 9)),
             (ID_SIZE_BYTES - 10) * BITS_PER_BYTE),
            
            (Id(BIN_ID0[:-1] + '\x06'),
             2),
            )
        id2_log = (
            (Id('\x41' * ID_SIZE_BYTES),
             Id('\x41' * ID_SIZE_BYTES),
             -1),

            (Id('\x41' * ID_SIZE_BYTES),
             Id('\x01' * ID_SIZE_BYTES),
             158),

            (Id('\x41' * ID_SIZE_BYTES),
             Id('\x43' * ID_SIZE_BYTES),
             153),
            )

        for (id_, log_) in id_log:
            logger.debug('log_distance: %d' % id0.log_distance(id_))
            logger.debug('expected: %d' % log_)
            eq_(id0.log_distance(id_), log_)
        for id1, id2, expected in id2_log:
            eq_(id1.log_distance(id2), expected)

            z = Id('\0'*20)
            eq_(z.log_distance(Id('\x00'*19+'\x00')), -1)
            eq_(z.log_distance(Id('\x00'*19+'\x00')), -1)
            eq_(z.log_distance(Id('\x00'*19+'\x00')), -1)
            eq_(z.log_distance(Id('\x00'*19+'\x00')), -1)
            eq_(z.log_distance(Id('\x00'*19+'\x00')), -1)



    def test_order_closest(self):
        id0 = Id(BIN_ID0)
        ordered_list = [
            Id('\x00' * ID_SIZE_BYTES),
            Id(BIN_ID0[:-1] + '\x06'),
            Id(BIN_ID0[:9] + '\x01' * (ID_SIZE_BYTES - 9)),
            Id(BIN_ID0[:7] + '\xff' * (ID_SIZE_BYTES - 7)),
            Id(BIN_ID0[:7] + '\xff' * (ID_SIZE_BYTES - 7)),
            Id('\x00' + '\xff' * (ID_SIZE_BYTES - 1)),
            Id('\x53' * ID_SIZE_BYTES),
            Id('\xff' * ID_SIZE_BYTES),
            ]
        random_list = random.sample(ordered_list, len(ordered_list))

        random_list_copy = random_list[:]

        logger.debug('ordered list')
        for e in ordered_list: logger.debug('%s' % e)
        logger.debug('random order')
        for e in random_list: logger.debug('%s' % e)

        result_list = id0.order_closest(random_list)
        logger.debug('order_closest result')
        for e in result_list: logger.debug('%s' % e)
        logger.debug('random order (it should not change)')
        for e in random_list: logger.debug('%s' % e)

        # make sure order_closest does not modify random_list
        assert random_list == random_list_copy
        
        for i, ordered_id in enumerate(ordered_list):
            logger.debug('%d, %s, %s' % (i, ordered_id, result_list[i]))
            assert ordered_id.bin_id == result_list[i].bin_id
            # Notice that 'assert ordered_id is result_id'
            # do not work when two Id instances have the same bin_id

    def test_generate_closest_id(self):
        id_ = RandomId()
        for i in [-1] + range(ID_SIZE_BITS):
            eq_(id_.log_distance(id_.generate_close_id(i)), i)

            
class TestRandomId:
    for i in xrange(123):
        assert RandomId() != RandomId()
