# Copyright (C) 2009 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

import random

from utils import log

import identifier as identifier
import message as message
from node import Node, RoutingNode
from routing_table import RoutingTable, RnodeNotFound, BucketFullError

#TODO2: Stop expelling nodes from tables when there are many consecutive
# timeouts (and enter off-line mode)

NUM_BUCKETS = identifier.ID_SIZE_BITS + 1
"""
We need (+1) to cover all the cases. See the following table:
Index | Distance      | Comment
0     | [2^0,2^1)     | All bits equal but the least significant bit
1     | [2^1,2^2)     | All bits equal till the second least significant bit
...
158   | [2^159,2^160) | The most significant bit is equal the second is not
159   | [2^159,2^160) | The most significant bit is different
-1    | 0             | The bit strings are equal
"""

DEFAULT_NUM_NODES = 8
NODES_PER_BUCKET = [] # 16, 32, 64, 128, 256]
NODES_PER_BUCKET[:0] = [DEFAULT_NUM_NODES] \
    * (NUM_BUCKETS - len(NODES_PER_BUCKET))

REFRESH_PERIOD = 10 * 60 # 10 minutes
QUARANTINE_PERIOD = 3 * 60 # 3 minutes

MAX_NUM_TIMEOUTS = 3
PING_DELAY_AFTER_TIMEOUT = 30 #seconds


MIN_RNODES_BOOTSTRAP = 50
NUM_NODES_PER_BOOTSTRAP_STEP = 10
BOOTSTRAP_DELAY = 1

BOOTSTRAP_MODE = 'bootstrap_node'
NORMAL_MODE = 'normal_mode'

MAX_CONCURRENT_REFRESH_MSGS = 20
NO_PRIORITY = 0
PRIORITY = 10

REFRESH_DELAY_FOR_NON_NS = .200 #seconds

class RoutingManager(object):
    
    def __init__(self, my_node, querier, bootstrap_nodes):
        self.my_node = my_node
        self.querier = querier
        #Copy the bootstrap list
        self.bootstrap_nodes = [n for n in bootstrap_nodes]
        
        self.main = RoutingTable(my_node, NODES_PER_BUCKET)
        self.replacement = RoutingTable(my_node, NODES_PER_BUCKET)
        self.ping_msg = message.OutgoingPingQuery(my_node.id)
        self.find_node_msg = message.OutgoingFindNodeQuery(
            my_node.id,
            my_node.id)
        self.mode = BOOTSTRAP_MODE
        self.num_concurrent_refresh_msgs = 0
        #This must be called by an external party: self.do_bootstrap()
        #After initializing callbacks

        # Add myself to the routing table
        rnode = self.main.add(my_node)
        self._reset_refresh_task(rnode)

    def do_bootstrap(self):
        if self.main.num_rnodes > MIN_RNODES_BOOTSTRAP:
            # Enough nodes. Stop bootstrap.
            return
        for _ in xrange(NUM_NODES_PER_BOOTSTRAP_STEP):
            if not self.bootstrap_nodes:
                self.mode = NORMAL_MODE
                return
            index = random.randint(0,
                                   len(self.bootstrap_nodes) - 1)
            self.querier.send_query(self.find_node_msg,
                                    self.bootstrap_nodes[index],
                                    self._do_nothing,
                                    self._do_nothing,
                                    self._do_nothing)
            del self.bootstrap_nodes[index]
        #TODO2: Don't use querier's rpc_m
        self.querier.rpc_m.call_later(BOOTSTRAP_DELAY,
                                      self.do_bootstrap)
    
    def on_query_received(self, node_):
        try:
            rnode = self.main.get_rnode(node_)
        except RnodeNotFound:
            pass # node is not in the main table
        else:
            # node in routing table: inform rnode
            rnode.on_query_received()
            self._reset_refresh_task(rnode)
            return
        # Node is not in routing table
        # Check reachability (if the bucket is not full)
        if self.main.there_is_room(node_):
            # there is room in the bucket: ping node to check reachability
            self._refresh_now(node_)
            return
        # No room in the main routing table
        # Add to replacement table (if the bucket is not full)
        bucket = self.replacement.get_bucket(node_)
        worst_rnode = self._worst_rnode(bucket.rnodes)
        if worst_rnode \
                and worst_rnode.timeouts_in_a_row() > MAX_NUM_TIMEOUTS:
            self.replacement.remove(worst_rnode)
            self.replacement.add(node_)

            
    def on_response_received(self, node_): #TODO2:, rtt=0):
        try:
            rnode = self.main.get_rnode(node_)
        except (RnodeNotFound):
            pass
        else:
            # node in routing table: refresh it
            rnode.on_response_received()
            self._reset_refresh_task(rnode)
            return
        # The node is not in main
        try:
            rnode = self.replacement.get_rnode(node_)
        except (RnodeNotFound):
            pass
        else:
            # node in replacement table
            # let's see whether there is room in the main
            rnode.on_response_received()
            if self.main.there_is_room(node_):
                rnode = self.main.add(rnode)
                self._reset_refresh_task(rnode)
                self.replacement.remove(rnode)
            return
        # The node is nowhere
        # Add to replacement table (if the bucket is not full)
        bucket = self.replacement.get_bucket(node_)
        if self.main.there_is_room(node_):
            if not bucket.rnodes:
                # Replacement is empty
                rnode = self.main.add(node_)
                self._reset_refresh_task(rnode)
                return
        # The main bucket is full or the repl bucket is not empty
        worst_rnode = self._worst_rnode(bucket.rnodes)
        # Get the worst node in replacement bucket and see whether
        # it's bad enough to be replaced by node_
        if worst_rnode \
                and worst_rnode.timeouts_in_a_row() > MAX_NUM_TIMEOUTS:
            # This node is better candidate than worst_rnode
            self.replacement.remove(worst_rnode)
        try:
            self.replacement.add(node_)
        except (BucketFullError):
            pass

        
    def on_error_received(self, node_):
        pass
    
    def on_timeout(self, node_):
        if node_ is self.my_node:
            raise Exception, 'I got a timeout from myself!!!' 
        if not node_.id:
            return # This is a bootstrap node (just addr, no id)
        try:
            rnode = self.main.get_rnode(node_)
        except RnodeNotFound:
            pass
        else:
            # node in routing table: check whether it should be removed
            rnode.on_timeout()
            replacement_bucket = self.replacement.get_bucket(node_)
            self._refresh_replacement_bucket(replacement_bucket)
            self.main.remove(rnode)
            try:
                self.replacement.add(rnode)
            except (BucketFullError):
                worst_rnode = self._worst_rnode(replacement_bucket.rnodes)
                if worst_rnode:
                    # Replace worst node in replacement table
                    self.replacement.remove(worst_rnode)
                    self._refresh_replacement_bucket(replacement_bucket)
                    # We don't want to ping the node which just did timeout
                    self.replacement.add(rnode)
        # Node is not in main table
        try:
            rnode = self.replacement.get_rnode(node_)
        except RnodeNotFound:
            pass # the node is not in any table. Nothing to do here.
        else:
            # Node in replacement table: just update rnode
            rnode.on_timeout()
            
    def on_nodes_found(self, nodes):
        #FIXME: this will send ping at exponential rate
        #not good!!!!
        log.debug('nodes found: %r', nodes)
        for node_ in nodes:
            try:
                rnode = self.main.get_rnode(node_)
            except RnodeNotFound:
                # Not in the main: ping it if there is room in main
                if self.main.there_is_room(node_):
                    log.debug('pinging node found: %r', node_)
                    self._refresh_now(node_, NO_PRIORITY)
                    #TODO2: prefer NS

    def get_closest_rnodes(self, target_id, num_nodes=DEFAULT_NUM_NODES):
        return self.main.get_closest_rnodes(target_id, num_nodes)

    def get_all_rnodes(self):
        return (self.main.get_all_rnodes(),
                self.replacement.get_all_rnodes())

    def _refresh_now(self, node_, priority=PRIORITY):
        if priority == NO_PRIORITY and \
                self.num_concurrent_refresh_msgs > MAX_CONCURRENT_REFRESH_MSGS:
            return
        self.num_concurrent_refresh_msgs += 1
        return self.querier.send_query(self.find_node_msg,
                                       node_,
                                       self._refresh_now_callback,
                                       self._refresh_now_callback,
                                       self._refresh_now_callback)
    
    def _reset_refresh_task(self, rnode):
        if rnode.refresh_task:
            # Cancel the current refresh task
            rnode.refresh_task.cancel()
        if rnode.in_quarantine:
            rnode.refresh_task = self._refresh_later(rnode,
                                                     QUARANTINE_PERIOD)
        else:
            rnode.refresh_task = self._refresh_later(rnode)


    def _refresh_later(self, rnode, delay=REFRESH_PERIOD):
        return self.querier.send_query_later(delay,
                                             self.find_node_msg,
                                             rnode,
                                             self._do_nothing,
                                             self._do_nothing,
                                             self._do_nothing)
    def _do_nothing(self, *args, **kwargs):
        pass

    def _refresh_now_callback(self, *args, **kwargs):
        self.num_concurrent_refresh_msgs -= 1


    def _refresh_replacement_bucket(self, bucket):
        for rnode in bucket.rnodes:
            if rnode.is_ns:
                # We give advantage to NS nodes
                self._refresh_now(rnode)
            else:
                self._refresh_later(rnode, REFRESH_DELAY_FOR_NON_NS)
    
    def _worst_rnode(self, rnodes):
        max_num_timeouts = -1
        worst_rnode_so_far = None
        for rnode in rnodes:
            num_timeouots = rnode.timeouts_in_a_row()
            if num_timeouots >= max_num_timeouts:
                max_num_timeouts = num_timeouots
                worst_rnode_so_far = rnode
        return worst_rnode_so_far

        
                
            
class RoutingManagerMock(object):

    def get_closest_rnodes(self, target_id):
        import test_const as tc
        if target_id == tc.INFO_HASH_ZERO:
            return (tc.NODES_LD_IH[155][4], 
                    tc.NODES_LD_IH[157][3],
                    tc.NODES_LD_IH[158][1],
                    tc.NODES_LD_IH[159][0],
                    tc.NODES_LD_IH[159][2],)
        else:
            return tc.NODES
