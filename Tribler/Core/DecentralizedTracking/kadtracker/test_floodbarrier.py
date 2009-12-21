# Copyright (C) 2009 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

import time

from utils import log

from test_const import *

from floodbarrier import FloodBarrier



class TestFloodBarrier:

    def setup(self):
        #log.critical('************* BEGIN **************')
        pass

    def test(self):
        fb = FloodBarrier(checking_period=.4,
                          max_packets_per_period=4,
                          blocking_period=1)
        for ip in IPS:
            for _ in xrange(4):
                assert not fb.ip_blocked(ip)
        # Every ip is on the limit
        assert fb.ip_blocked(IPS[0])
        assert fb.ip_blocked(IPS[1])
        # 0 and 3 blocked
        time.sleep(.2)
        # Half a period gone
        assert fb.ip_blocked(IPS[0])
        # IP 0 refreshes the blocking (extra .2 seconds)
        time.sleep(.2)
        # The initial floods are forgotten
        # IP 0,1,3 are blocked
        assert fb.ip_blocked(IPS[0])
        # The blocking doesn't get refreshed now (.8 secs to expire)
        assert fb.ip_blocked(IPS[1])
        # The blocking doesn't get refreshed (.6 secs to expire)
        assert not fb.ip_blocked(IPS[2])
        time.sleep(.7)
        # IP 0 is the only one still blocked (it got refreshed)
        assert fb.ip_blocked(IPS[0])
        assert not fb.ip_blocked(IPS[1])
        assert not fb.ip_blocked(IPS[2])
        assert not fb.ip_blocked(IPS[3])
        time.sleep(.4)
        for ip in IPS:
            for _ in xrange(4):
                assert not fb.ip_blocked(ip)
        time.sleep(.4)
        for ip in IPS:
            for _ in xrange(4):
                assert not fb.ip_blocked(ip)

        
