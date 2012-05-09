# Copyright (C) 2009-2010 Raul Jimenez, Flutra Osmani
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

from nose.tools import eq_, ok_, assert_raises
import ptime as time
import tracker

import logging, logging_conf

logging_conf.testing_setup(__name__)
logger = logging.getLogger('dht')


VALIDITY_PERIOD = 30
CLEANUP_COUNTER = 5
KEYS = ('0','1','2')
PEERS = [('1.2.3.4', i) for i in range(0, 10)]


class TestTracker(object):

    def setup(self):
        time.mock_mode()
        self.t = tracker.Tracker(VALIDITY_PERIOD, CLEANUP_COUNTER)

    def test_put(self):
        eq_(self.t.num_keys, 0)
        eq_(self.t.num_peers, 0)
        self.t.put(KEYS[0], PEERS[0])
        eq_(self.t.num_keys, 1)
        eq_(self.t.num_peers, 1)

    def test_get_empty_key(self):
        eq_(self.t.get(KEYS[0]), [])

    def test_remove_duplicates(self):
        self.t.put(KEYS[0], PEERS[0])
        self.t.put(KEYS[0], PEERS[0])
        eq_(self.t.num_peers, 1)
        self.t.put(KEYS[0], PEERS[1])
        eq_(self.t.get(KEYS[0]), PEERS[0:2])

    def test_does_not_leak_memory(self):
        for i in range(CLEANUP_COUNTER - 1):
            self.t.put(KEYS[0], PEERS[i])
        eq_(self.t.num_keys, 1)
        eq_(self.t.num_peers, CLEANUP_COUNTER - 1)
        # This sleep makes all entries expired
        time.sleep(30)
        # But does not trigger any cleaning up
        eq_(self.t.num_keys, 1)
        eq_(self.t.num_peers, CLEANUP_COUNTER - 1)
        # This put triggers a clean up
        self.t.put(KEYS[1], PEERS[0])
        # The expired entries are no more
        eq_(self.t.num_keys, 1)
        eq_(self.t.num_peers, 1)
        
    def test_get_nonempty_key(self):
        self.t.put(KEYS[0], PEERS[0])
        print self.t._tracker_dict
        eq_(self.t.get(KEYS[0]), [PEERS[0]])
        
    def test_get_expired_value(self):
        self.t.put(KEYS[0], PEERS[0])
        eq_(self.t.num_keys, 1)
        eq_(self.t.num_peers, 1)
        time.sleep(30)
        eq_(self.t.get(KEYS[0]), [])
        #eq_(self.t.num_keys, 0)
        eq_(self.t.num_peers, 0)

    def test_many_puts_and_gets(self):
        # 0
        self.t.put(KEYS[0], PEERS[0])
        time.sleep(20)
        # 20
        self.t.put(KEYS[0], PEERS[0])
        time.sleep(20)
        # 40 
        self.t.put(KEYS[0], PEERS[1])
        eq_(self.t.get(KEYS[0]), PEERS[0:2])
        time.sleep(10)
        # 50
        self.t.put(KEYS[0], PEERS[0])
        eq_(self.t.get(KEYS[0]), PEERS[1::-1])
        time.sleep(20)
        # 70
        eq_(self.t.get(KEYS[0]), PEERS[0:1])
        time.sleep(10)
        # 80
        eq_(self.t.get(KEYS[0]), [])

    def test_hundred_puts(self):
        # test > 5 puts
        eq_(self.t.num_peers, 0)

        time.sleep(0)
        eq_(self.t.num_peers, 0)

        self.t.put(1,1)
        eq_(self.t.num_peers, 1)

        time.sleep(25)
        eq_(self.t.num_peers, 1)

        self.t.put(2,2)
        eq_(self.t.num_peers, 2)

        time.sleep(1)
        eq_(self.t.num_peers, 2)

        self.t.put(3,3)
        eq_(self.t.num_peers, 3)

        time.sleep(1)
        eq_(self.t.num_peers, 3)

        self.t.put(4,4)
        eq_(self.t.num_peers, 4)

        time.sleep(3)
        eq_(self.t.num_peers, 4)

        self.t.put(5,5)
        # cleaning... 1 out
        eq_(self.t.num_peers, 4)

        time.sleep(.0)
        eq_(self.t.num_peers, 4)

        self.t.put(6,6)
        eq_(self.t.num_peers, 5)

        time.sleep(.00)
        eq_(self.t.num_peers, 5)

        self.t.put(7,7)
        eq_(self.t.num_peers, 6)

        time.sleep(20)
        eq_(self.t.num_peers, 6)

        self.t.put(8,8)
        eq_(self.t.num_peers, 7)

        time.sleep(.00)
        eq_(self.t.num_peers, 7)

        self.t.put(9,9)
        eq_(self.t.num_peers, 8)

        time.sleep(10)
        eq_(self.t.num_peers, 8)

        self.t.put(0,0)
        # cleaning ... 2,3,4,5,6,7 out
        eq_(self.t.num_peers, 3)

            
    def teardown(self):
        time.normal_mode()

