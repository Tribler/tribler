# Copyright (C) 2009 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

from nose.tools import ok_, eq_, raises, assert_raises
import test_const as tc

import logging, logging_conf

import utils
from identifier import Id, ID_SIZE_BYTES
from node import Node, RoutingNode
from node import LAST_RTT_W

logging_conf.testing_setup(__name__)
logger = logging.getLogger('dht')



bin_id1 = '1' * ID_SIZE_BYTES
bin_id2 = '2' * ID_SIZE_BYTES
id1 = Id(bin_id1)
id2 = Id(bin_id2)
addr1 = ('127.0.0.1', 1111)
addr2 = ('127.0.0.1', 2222)


class TestNode:

    def setup(self):
        pass
    
    def test_node(self):
        node1 = Node(addr1, id1)
        node2 = Node(addr2, id2)
        node1b = Node(addr1, None)
        node1ip = Node(('127.0.0.2', 1111), id1)
        node1port = Node(addr2, id1)
        node1id = Node(addr1, id2)

        assert str(node1) == '<node: %r %r>' % (addr1, id1)
        #<node: ('127.0.0.1', 1111) 0x1313131313131313131313131313131313131313>

        assert node1.id == id1
        assert node1.id != id2
        assert node1.addr == addr1
        assert node1.addr != addr2
        assert node1 == node1

        assert node1 != node1b
        node1b.id = id1
        assert node1 == node1b

        assert node1 != node2
        assert node1 != node1ip
        assert node1 != node1port
        assert node1 != node1id

    def test_compact_addr(self):
        eq_(tc.CLIENT_NODE.compact_addr,
            utils.compact_addr(tc.CLIENT_ADDR))

    def test_log_distance(self):
        eq_(tc.CLIENT_NODE.log_distance(tc.SERVER_NODE),
            tc.CLIENT_ID.log_distance(tc.SERVER_ID))

    def test_compact(self):
        eq_(tc.CLIENT_NODE.compact(),
            tc.CLIENT_ID.bin_id + utils.compact_addr(tc.CLIENT_ADDR))
        
    def test_get_rnode(self):
        eq_(tc.CLIENT_NODE.get_rnode(),
            RoutingNode(tc.CLIENT_NODE))
        
    @raises(AttributeError)
    def test_node_exceptions(self):
        Node(addr1, id1).id = id2

        

class TestRoutingNode:

    def setup(self):
        self.rnode1 = RoutingNode(Node(addr1, id1))
        self.rnode2 = RoutingNode(Node(addr2, id2))

    def test_rnode(self):
        RTT1 = 1
        RTT2 = 2
        assert self.rnode1.timeouts_in_a_row() == 0
        self.rnode1.on_timeout()
        self.rnode1.on_timeout()
        self.rnode1.on_timeout()
        assert self.rnode1.timeouts_in_a_row() == 3
        assert self.rnode1.timeouts_in_a_row(False) == 3
        self.rnode1.on_query_received()
        assert self.rnode1.timeouts_in_a_row() == 0
        eq_(self.rnode1.timeouts_in_a_row(False), 3)
        self.rnode1.on_response_received(1)
        assert self.rnode1.timeouts_in_a_row() == 0
        assert self.rnode1.timeouts_in_a_row(False) == 0
        assert self.rnode1._num_queries == 1
        assert self.rnode1._num_responses == 1
        assert self.rnode1._num_timeouts == 3        
        self.rnode1.on_response_received(RTT1)
        self.rnode1.on_response_received(RTT1)
        self.rnode1.on_response_received(RTT1)
        self.rnode1.on_response_received(RTT1)
        self.rnode1.on_response_received(RTT1)
        self.rnode1.on_response_received(RTT1)
        self.rnode1.on_response_received(RTT1)
        self.rnode1.on_response_received(RTT2)
        eq_(self.rnode1._rtt_avg,
            RTT1 * (1 - LAST_RTT_W) + RTT2 * LAST_RTT_W)
        self.rnode1.on_timeout()
        self.rnode1.on_timeout()
        
    def _test_rank(self):
        eq_(self.rnode1.rank(), 0)
        self.rnode1.on_query_received()
        eq_(self.rnode1.rank(), 0)
        self.rnode1.on_response_received()
        eq_(self.rnode1.rank(), 1)

    def test_repr(self):
        _ = repr(RoutingNode(tc.CLIENT_NODE))

    def test_get_rnode(self):
        eq_(self.rnode1.get_rnode(),
            self.rnode1)
