# Copyright (C) 2009 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

import logging, logging_conf

from nose.tools import eq_, ok_, assert_raises

import test_const as tc

import node

from routing_table import *

logging_conf.testing_setup(__name__)
logger = logging.getLogger('dht')


class TestRoutingTable:

    def setup(self):
        nodes_per_bucket = [2] * 161
        self.rt = RoutingTable(tc.CLIENT_NODE,
                               nodes_per_bucket)

    def test_basics(self):
        eq_(self.rt.get_bucket(tc.SERVER_NODE).rnodes, [])
        ok_(self.rt.there_is_room(tc.SERVER_NODE))
        assert_raises(RnodeNotFound, self.rt.get_rnode, tc.SERVER_NODE)
        ok_(not self.rt.get_bucket(tc.SERVER_NODE).is_full())
        eq_(self.rt.num_rnodes, 0)
        eq_(self.rt.get_all_rnodes(), [])

        self.rt.add(tc.SERVER_NODE)
        ok_(self.rt.there_is_room(tc.SERVER_NODE))
        eq_(self.rt.get_bucket(tc.SERVER_NODE).rnodes, [tc.SERVER_NODE])
        eq_(self.rt.get_rnode(tc.SERVER_NODE), tc.SERVER_NODE)
        ok_(not self.rt.get_bucket(tc.SERVER_NODE).is_full())
        eq_(self.rt.num_rnodes, 1)
        eq_(self.rt.get_all_rnodes(), [tc.SERVER_NODE])
        
        # Let's add a node to the same bucket
        new_node = node.Node(tc.SERVER_NODE.addr,
                             tc.SERVER_NODE.id.generate_close_id(1))
        self.rt.add(new_node)
        # full bucket
        ok_(not self.rt.there_is_room(tc.SERVER_NODE))
        eq_(self.rt.get_bucket(new_node).rnodes, [tc.SERVER_NODE, new_node])
        eq_(self.rt.get_rnode(new_node), new_node)
        ok_(self.rt.get_bucket(tc.SERVER_NODE).is_full())
        eq_(self.rt.num_rnodes, 2)
        eq_(self.rt.get_all_rnodes(), [tc.SERVER_NODE, new_node])


        eq_(self.rt.get_closest_rnodes(tc.SERVER_ID, 1),
            [tc.SERVER_NODE])
        eq_(self.rt.get_closest_rnodes(tc.SERVER_ID),
            [tc.SERVER_NODE, new_node])

        assert_raises(BucketFullError, self.rt.add, new_node)
        
        self.rt.remove(new_node)
        # there is one slot in the bucket
        ok_(self.rt.there_is_room(tc.SERVER_NODE))
        assert_raises(RnodeNotFound, self.rt.get_rnode, new_node)
        eq_(self.rt.get_bucket(tc.SERVER_NODE).rnodes, [tc.SERVER_NODE])
        eq_(self.rt.get_rnode(tc.SERVER_NODE), tc.SERVER_NODE)
        ok_(not self.rt.get_bucket(tc.SERVER_NODE).is_full())
        eq_(self.rt.num_rnodes, 1)
        eq_(self.rt.get_all_rnodes(), [tc.SERVER_NODE])

                             
        eq_(self.rt.get_closest_rnodes(tc.SERVER_ID), [tc.SERVER_NODE])
        
    def test_complete_coverage(self):
        str(self.rt.get_bucket(tc.SERVER_NODE))
        repr(self.rt)
