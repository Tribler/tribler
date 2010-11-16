# Copyright (C) 2009 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

import test_const as tc

import kadtracker

class TestKadTracker:

    def _callback(self, *args, **kwargs):
        return
    
    def setup(self):
        self.dht = kadtracker.KadTracker(tc.CLIENT_ADDR, '.')

    def test_all(self):
        #self.dht.start()
        self.dht.get_peers(tc.INFO_HASH, self._callback, tc.BT_PORT)
        self.dht.stop()
