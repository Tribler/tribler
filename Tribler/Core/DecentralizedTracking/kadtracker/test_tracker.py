# Copyright (C) 2009 Raul Jimenez, Flutra Osmani
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

from nose.tools import *

import time

import tracker
import minitwisted


keys = ('1','2')
peers = (('1.2.3.4', 1234), ('2.3.4.5', 2222))

class TestTracker(object):

    def setup(self):
        self.t = tracker.Tracker(.01, 5)

    def test_put(self):
        self.t.put(keys[0], peers[0])

    def test_get_empty_key(self):
        eq_(self.t.get(keys[0]), [])

    def test_get_nonempty_key(self):
        self.t.put(keys[0], peers[0])
        eq_(self.t.get(keys[0]), [peers[0]])
        
    def test_get_expired_value(self):
        self.t.put(keys[0], peers[0])
        time.sleep(.015)
        eq_(self.t.get(keys[0]), [])

    def test_many_puts_and_gets(self):
        #0
        self.t.put(keys[0], peers[0])
        time.sleep(.02)
        #.02
        self.t.put(keys[0], peers[0])
        time.sleep(.02)
        #.04
        self.t.put(keys[0], peers[1])
        eq_(self.t.get(keys[0]), [peers[0], peers[1]])
        time.sleep(.07)
        #.11
        self.t.put(keys[0], peers[0])
        eq_(self.t.get(keys[0]), [peers[1], peers[0]])
        time.sleep(.02)
        #.13
        eq_(self.t.get(keys[0]), [peers[0]])

    def test_hundred_puts(self):
        # test > 5 puts
        eq_(len(self.t.debug_view()), 0)
        time.sleep(0)
        eq_(len(self.t.debug_view()), 0)
        self.t.put(1,1)
        eq_(len(self.t.debug_view()), 1)
        time.sleep(.006)
        eq_(len(self.t.debug_view()), 1)
        self.t.put(2,2)
        eq_(len(self.t.debug_view()), 2)
        time.sleep(.004)
        eq_(len(self.t.debug_view()), 2)
        self.t.put(3,3)
        eq_(len(self.t.debug_view()), 3)
        time.sleep(.0)
        eq_(len(self.t.debug_view()), 3)
        self.t.put(4,4)
        eq_(len(self.t.debug_view()), 4)
        time.sleep(.0)
        eq_(len(self.t.debug_view()), 4)
        self.t.put(5,5)
        # cleaning... 1 out
        eq_(len(self.t.debug_view()), 4)
        time.sleep(.0)
        eq_(len(self.t.debug_view()), 4)
        self.t.put(6,6)
        eq_(len(self.t.debug_view()), 5)
        time.sleep(.00)
        eq_(len(self.t.debug_view()), 5)
        self.t.put(7,7)
        eq_(len(self.t.debug_view()), 6)
        time.sleep(.01)
        eq_(len(self.t.debug_view()), 6)
        self.t.put(8,8)
        eq_(len(self.t.debug_view()), 7)
        time.sleep(.00)
        eq_(len(self.t.debug_view()), 7)
        self.t.put(9,9)
        eq_(len(self.t.debug_view()), 8)
        time.sleep(.00)
        eq_(len(self.t.debug_view()), 8)
        self.t.put(0,0)
        # cleaning ... 2,3,4,5,6,7 out
        eq_(len(self.t.debug_view()), 3)

            
    def teardown(self):
        pass
