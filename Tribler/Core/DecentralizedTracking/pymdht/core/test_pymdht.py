# Copyright (C) 2009-2010 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

import test_const as tc

import pymdht

import routing_plugin_template as routing_m_mod
import lookup_plugin_template as lookup_m_mod

class TestKadTracker:

    def _callback(self, *args, **kwargs):
        return
    
    def setup(self):
        self.dht = pymdht.Pymdht(tc.CLIENT_ADDR, 'test_logs',
                                 routing_m_mod,
                                 lookup_m_mod)

    def test_interface(self):
        #self.dht.start()
        self.dht.get_peers(None, tc.INFO_HASH, self._callback, tc.BT_PORT)
        self.dht.stop()
        self.dht.print_routing_table_stats()
