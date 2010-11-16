# Copyright (C) 2009-2010 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information
"""
This module intends to implement the routing policy specified in BEP5:

-
-
-
-

"""


import random
import core.ptime as time
import heapq

import logging

import core.identifier as identifier
import core.message as message
from core.querier import Query
import core.node as node
from core.node import Node, RoutingNode
from core.routing_table import RoutingTable

logger = logging.getLogger('dht')

NUM_BUCKETS = identifier.ID_SIZE_BITS
"""
We need 160 sbuckets to cover all the cases. See the following table:
Index | Distance      | Comment
0     | [2^0,2^1)     | All bits equal but the least significant bit
1     | [2^1,2^2)     | All bits equal till the second least significant bit
...
158   | [2^159,2^160) | The most significant bit is equal the second is not
159   | [2^159,2^160) | The most significant bit is different

IMPORTANT: Notice there is NO bucket for -1
-1    | 0             | The bit strings are equal
"""

DEFAULT_NUM_NODES = 8
NODES_PER_BUCKET = [] # 16, 32, 64, 128, 256]
NODES_PER_BUCKET[:0] = [DEFAULT_NUM_NODES] \
    * (NUM_BUCKETS - len(NODES_PER_BUCKET))

REFRESH_PERIOD = 15 * 60 # 15 minutes
QUARANTINE_PERIOD = 3 * 60 # 3 minutes

MAX_NUM_TIMEOUTS = 2
PING_DELAY_AFTER_TIMEOUT = 30 #seconds


MIN_RNODES_BOOTSTRAP = 10
NUM_NODES_PER_BOOTSTRAP_STEP = 1

BOOTSTRAP_MODE = 'bootstrap_mode'
FIND_NODES_MODE = 'find_nodes_mode'
NORMAL_MODE = 'normal_mode'
_MAINTENANCE_DELAY = {BOOTSTRAP_MODE: .2,
                     FIND_NODES_MODE: 2,
                     NORMAL_MODE: 2}


class RoutingManager(object):
    
    def __init__(self, my_node, bootstrap_nodes):
        self.my_node = my_node
        #Copy the bootstrap list
        self.bootstrap_nodes = iter(bootstrap_nodes)
        
        self.table = RoutingTable(my_node, NODES_PER_BUCKET)
        self.ping_msg = message.OutgoingPingQuery(my_node.id)
        self.find_closest_msg = message.OutgoingFindNodeQuery(
            my_node.id,
            my_node.id)

        # maintenance variables
        self._maintenance_mode = BOOTSTRAP_MODE
        self._pinged_q_rnodes = {} # questionable nodes which have been
        # recently pinged
        self._maintenance_tasks = [self._refresh_stale_bucket,
            #self._ping_a_staled_rnode,
            # self._ping_a_query_received_node,
            # self._ping_a_found_node,
                                   ]
        
    def do_maintenance(self):
        queries_to_send = []
        maintenance_lookup_target = None
        if self._maintenance_mode == BOOTSTRAP_MODE:
            try:
                node_ = self.bootstrap_nodes.next()
                queries_to_send = [self._get_maintenance_query(node_)]
            except (StopIteration):
                maintenance_lookup_target = self.my_node.id
                self._maintenance_mode = FIND_NODES_MODE
                return (10, [], maintenance_lookup_target)
        else:
            maintenance_lookup_target = self._refresh_stale_bucket()
        
        return (_MAINTENANCE_DELAY[self._maintenance_mode],
                queries_to_send, maintenance_lookup_target)
    
    def _refresh_stale_bucket(self):
        maintenance_lookup_target = None
        current_time = time.time()
        for i in xrange(self.table.lowest_index, NUM_BUCKETS):
            sbucket = self.table.get_sbucket(i)
            m_bucket = sbucket.main
            if not m_bucket:
                continue
            inactivity_time = current_time - m_bucket.last_changed_ts
            if inactivity_time > REFRESH_PERIOD:
#                print time.time(), '>>>>>>>>>>>>>>> refreshing bucket %d after %f secs' % (
#                    i, inactivity_time)
                maintenance_lookup_target = self.my_node.id.generate_close_id(
                    i)
                m_bucket.last_changed_ts = current_time
                return maintenance_lookup_target
        self._maintenance_mode = NORMAL_MODE
        return None

    def _get_maintenance_query(self, node_):
        return Query(self.ping_msg, node_)
         
    def on_query_received(self, node_):
        '''
        Return None when nothing to do
        Return a list of queries when queries need to be sent (the queries
        will be sent out by the caller)
        '''
        if self._maintenance_mode != NORMAL_MODE:
            return
        log_distance = self.my_node.log_distance(node_)
        try:
            sbucket = self.table.get_sbucket(log_distance)
        except(IndexError):
            return # Got a query from myself. Just ignore it.

        m_bucket = sbucket.main
        rnode = m_bucket.get_rnode(node_)
        if rnode:
            # node in routing table: inform rnode
            self._update_rnode_on_query_received(rnode)
            return
        
        # node is not in the routing table
        if m_bucket.there_is_room():
            # There is room in the bucket. Just add the new node.
            rnode = node_.get_rnode(log_distance)
            m_bucket.add(rnode)
            self.table.update_lowest_index(log_distance)
            self.table.num_rnodes += 1
            self._update_rnode_on_query_received(rnode)
            return
        # No room in the main routing table
        # Check whether there is a bad node to be replaced.
        bad_rnode = self._pop_bad_rnode(m_bucket)
        if bad_rnode:
            # We have a bad node in the bucket. Replace it with the new node.
            rnode = node_.get_rnode(log_distance)
            m_bucket.add(rnode)
            self._update_rnode_on_query_received(rnode)
            self.table.update_lowest_index(log_distance)
            self.table.num_rnodes += 0
            return

        # No bad nodes. Check for questionable nodes
        q_rnodes = self._get_questionable_rnodes(m_bucket)
        queries_to_send = []
#        if q_rnodes:
#            print time.time(), '-----pinging questionable nodes in',
#            print log_distance
#            print q_rnodes
        for q_rnode in q_rnodes:
            # Ping questinable nodes to check whether they are still alive.
            # (0 timeouts so far, candidate node)
            c_rnode = node_.get_rnode(log_distance)
            self._update_rnode_on_query_received(c_rnode)
            self._pinged_q_rnodes[q_rnode] = [0, c_rnode]
            queries_to_send.append(Query(self.ping_msg, q_rnode))
        return queries_to_send
  
    def on_response_received(self, node_, rtt, nodes):
        log_distance = self.my_node.log_distance(node_)
        try:
            sbucket = self.table.get_sbucket(log_distance)
        except(IndexError):
            return # Got a response from myself. Just ignore it.
        m_bucket = sbucket.main
        rnode = m_bucket.get_rnode(node_)
        if rnode:
            # node in routing table: update
            self._update_rnode_on_response_received(rnode, rtt)
            if self._maintenance_mode == NORMAL_MODE:
                m_bucket.last_changed_ts = time.time()
            if node_ in self._pinged_q_rnodes:
                # This node is questionable. This response proves that it is
                # alive. Remove it from the questionable dict.
                del self._pinged_q_rnodes[node_]
            return

        # The node is not in main
        if m_bucket.there_is_room():
            rnode = node_.get_rnode(log_distance)
            m_bucket.add(rnode)
            self.table.update_lowest_index(log_distance)
            self.table.num_rnodes += 1
            self._update_rnode_on_response_received(rnode, rtt)
            if self._maintenance_mode == NORMAL_MODE:
                m_bucket.last_changed_ts = time.time()
            return
        # The main bucket is full

        # if there is a bad node inside the bucket,
        # replace it with the sending node_
        bad_rnode = self._pop_bad_rnode(m_bucket)
        if bad_rnode:
            rnode = node_.get_rnode(log_distance)
            m_bucket.add(rnode)
            self._update_rnode_on_response_received(rnode, rtt)
            if self._maintenance_mode == NORMAL_MODE:
                m_bucket.last_changed_ts = time.time()
            self.table.update_lowest_index(log_distance)
            self.table.num_rnodes += 0
            return

        # There are no bad nodes. Ping questionable nodes (if any)
        q_rnodes = self._get_questionable_rnodes(m_bucket)
        queries_to_send = []
        for q_rnode in q_rnodes:
            # (0 timeouts so far, candidate node)
            c_rnode = node_.get_rnode(log_distance)
            self._update_rnode_on_response_received(c_rnode, rtt)
            self._pinged_q_rnodes[q_rnode] = [0, c_rnode]
            queries_to_send.append(Query(self.ping_msg, q_rnode))
        return queries_to_send
 
    def _pop_bad_rnode(self, mbucket):
        for rnode in mbucket.rnodes:
            if rnode.timeouts_in_a_row() >= 2:
                mbucket.remove(rnode)
                return rnode

    def _get_questionable_rnodes(self, m_bucket):
        q_rnodes = []
        for rnode in m_bucket.rnodes:
            inactivity_time = time.time() - rnode.last_seen
            if inactivity_time > REFRESH_PERIOD:
                q_rnodes.append(rnode)
            if rnode.num_responses == 0:
                q_rnodes.append(rnode)
        return q_rnodes
        
    def on_error_received(self, node_):
        pass
    
    def on_timeout(self, node_):
        if not node_.id:
            return # This is a bootstrap node (just addr, no id)
        log_distance = self.my_node.log_distance(node_)
        try:
            sbucket = self.table.get_sbucket(log_distance)
        except (IndexError):
            return # Got a timeout from myself, WTF? Just ignore.
        m_bucket = sbucket.main
        rnode = m_bucket.get_rnode(node_)

        if not rnode:
            # This node is not in the table. Nothing to do here
            return

        # The node is in the table. Update it
        self._update_rnode_on_timeout(rnode)
        t_strikes, c_rnode = self._pinged_q_rnodes.get(node_, (None, None))
        if t_strikes is None:
            # The node is not being checked by a "questinable ping".
            return
        elif t_strikes == 0:
            # This is the first timeout
            self._pinged_q_rnodes[node_] = (1, c_rnode)
            # Let's give it another chance
            return [Query(self.ping_msg, rnode)]
        elif t_strikes == 1:
            # Second timeout. You're a bad node, replace if possible
            # check if the candidate node is in the routing table
            log_distance = self.my_node.log_distance(c_rnode)
            m_bucket = self.table.get_sbucket(log_distance).main
            c_rnode_in_table = m_bucket.get_rnode(c_rnode)
            if c_rnode_in_table:
                print 'questionable node replaced'
                # replace
                m_bucket.remove(rnode)
                m_bucket.add(c_rnode)
                self.table.update_lowest_index(log_distance)
                self.table.num_rnodes += 0                    
        
    def get_closest_rnodes(self, log_distance, num_nodes, exclude_myself):
        if not num_nodes:
            num_nodes = NODES_PER_BUCKET[log_distance]
        return self.table.get_closest_rnodes(log_distance, num_nodes,
                                             exclude_myself)

    def get_main_rnodes(self):
        return self.table.get_main_rnodes()

    def print_stats(self):
        self.table.print_stats()

    def _update_rnode_on_query_received(self, rnode):
        """Register a query from node.

        You should call this method when receiving a query from this node.

        """
        current_time = time.time()
        rnode.last_action_ts = time.time()
        rnode.msgs_since_timeout += 1
        rnode.num_queries += 1
        rnode.add_event(current_time, node.QUERY)
        rnode.last_seen = current_time

    def _update_rnode_on_response_received(self, rnode, rtt):
        """Register a reply from rnode.

        You should call this method when receiving a response from this rnode.

        """
        rnode.rtt = rtt
        current_time = time.time()
        #rnode._reset_refresh_task()
        if rnode.in_quarantine:
            rnode.in_quarantine = rnode.last_action_ts < (
                current_time - QUARANTINE_PERIOD)
        rnode.last_action_ts = current_time
        rnode.num_responses += 1
        rnode.add_event(time.time(), node.RESPONSE)
        rnode.last_seen = current_time

    def _update_rnode_on_timeout(self, rnode):
        """Register a timeout for this rnode.

        You should call this method when getting a timeout for this node.

        """
        rnode.last_action_ts = time.time()
        rnode.msgs_since_timeout = 0
        rnode.num_timeouts += 1
        rnode.add_event(time.time(), node.TIMEOUT)

    def _worst_rnode(self, rnodes):
        max_num_timeouts = -1
        worst_rnode_so_far = None
        for rnode in rnodes:
            num_timeouots = rnode.timeouts_in_a_row()
            if num_timeouots >= max_num_timeouts:
                max_num_timeouts = num_timeouots
                worst_rnode_so_far = rnode
        return worst_rnode_so_far
