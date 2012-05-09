# Copyright (C) 2009-2010 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

import ptime as time

from nose.tools import ok_, eq_, raises, assert_raises
import test_const as tc

import logging, logging_conf

import utils
from identifier import Id, ID_SIZE_BYTES
from node import Node, RoutingNode
import node

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
        node1 = Node(addr1, id1, 'version')
        node2 = Node(addr2, id2)
        node1b = Node(addr1, None)
        node1ip = Node(('127.0.0.2', 1111), id1)
        node1port = Node(addr2, id1)
        node1id = Node(addr1, id2)

        eq_(str(node1), '<node: %26r %r (version)>' % (addr1, id1))
        #<node: ('127.0.0.1', 1111) 0x1313131313131313131313131313131313131313>

        eq_(node1.id, id1)
        assert node1.id != id2
        assert node1.addr == addr1
        eq_(node1.ip, addr1[0])
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

    def test_distance(self):
        eq_(tc.CLIENT_NODE.distance(tc.SERVER_NODE),
            tc.CLIENT_ID.distance(tc.SERVER_ID))

    def test_compact(self):
        eq_(tc.CLIENT_NODE.compact(),
            tc.CLIENT_ID.bin_id + utils.compact_addr(tc.CLIENT_ADDR))
        
    def test_get_rnode(self):
        eq_(tc.CLIENT_NODE.get_rnode(1),
            RoutingNode(tc.CLIENT_NODE, 1))
        
    @raises(AttributeError)
    def test_node_exceptions(self):
        Node(addr1, id1).id = id2

    def test_node_without_id(self):
        n1 = Node(tc.CLIENT_ADDR)
        n2 = Node(tc.CLIENT_ADDR)
        eq_(n1, n2)
        n1.id = tc.CLIENT_ID
        ok_(n1 != n2)
        n2.id = tc.CLIENT_ID
        eq_(n1, n2)

class TestRoutingNode:

    def setup(self):
        self.rnode1 = RoutingNode(Node(addr1, id1), 1)
        self.rnode2 = RoutingNode(Node(addr2, id2), 1)

    def test_timeouts_in_a_row(self):
        rnode = RoutingNode(tc.NODES[0], 1)
        eq_(rnode.timeouts_in_a_row(), 0)
        eq_(rnode.timeouts_in_a_row(True), 0)
        eq_(rnode.timeouts_in_a_row(False), 0)
        # got query
        rnode.add_event(time.time(), node.QUERY)
        eq_(rnode.timeouts_in_a_row(), 0)
        eq_(rnode.timeouts_in_a_row(True), 0)
        eq_(rnode.timeouts_in_a_row(False), 0)
        # got timeout
        rnode.add_event(time.time(), node.TIMEOUT)
        eq_(rnode.timeouts_in_a_row(), 1)
        eq_(rnode.timeouts_in_a_row(True), 1)
        eq_(rnode.timeouts_in_a_row(False), 1)
        # got query
        rnode.add_event(time.time(), node.QUERY)
        eq_(rnode.timeouts_in_a_row(), 0)
        eq_(rnode.timeouts_in_a_row(True), 0)
        eq_(rnode.timeouts_in_a_row(False), 1)
        # got timeout
        rnode.add_event(time.time(), node.TIMEOUT)
        eq_(rnode.timeouts_in_a_row(), 1)
        eq_(rnode.timeouts_in_a_row(True), 1)
        eq_(rnode.timeouts_in_a_row(False), 2)
        # got response
        rnode.add_event(time.time(), node.RESPONSE)
        eq_(rnode.timeouts_in_a_row(), 0)
        eq_(rnode.timeouts_in_a_row(True), 0)
        eq_(rnode.timeouts_in_a_row(False), 0)
        
    def test_repr(self):
        _ = repr(RoutingNode(tc.CLIENT_NODE, 1))

    def test_get_node_and_get_rnode(self):
        rn1 = self.rnode1.get_rnode()
        eq_(rn1, self.rnode1)
        n1 = rn1.get_node()
        eq_(n1, rn1)
        rn1_duplicate = n1.get_rnode(1)
        eq_(rn1_duplicate, rn1)
