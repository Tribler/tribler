# Copyright (C) 2009-2010 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information
"""
This module intends to implement the routing policy specified in NICE RTT:

-
-
-
-

"""


import random
import heapq

import logging

try:
    import core.ptime as time
    import core.identifier as identifier
    import core.message as message
    from core.querier import Query
    import core.node as node
    from core.node import Node, RoutingNode
    from core.routing_table import RoutingTable
except (ImportError):
    import Tribler.Core.DecentralizedTracking.pymdht.core.ptime as time
    import Tribler.Core.DecentralizedTracking.pymdht.core.identifier as identifier
    import Tribler.Core.DecentralizedTracking.pymdht.core.message as message
    from Tribler.Core.DecentralizedTracking.pymdht.core.querier import Query
    import Tribler.Core.DecentralizedTracking.pymdht.core.node as node
    from Tribler.Core.DecentralizedTracking.pymdht.core.node import Node, RoutingNode
    from Tribler.Core.DecentralizedTracking.pymdht.core.routing_table import RoutingTable

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
FIND_CLOSEST_MODE = 'find_closest_mode'
NORMAL_MODE = 'normal_mode'
_MAINTENANCE_DELAY = {BOOTSTRAP_MODE: .2,
                     FIND_CLOSEST_MODE: 3,
                     NORMAL_MODE: 6}


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
        self._next_stale_maintenance_index = 0
        self._maintenance_mode = BOOTSTRAP_MODE
        self._replacement_queue = _ReplacementQueue(self.table)
        self._query_received_queue = _QueryReceivedQueue(self.table)
        self._found_nodes_queue = _FoundNodesQueue(self.table)
        self._maintenance_tasks = [self._ping_a_staled_rnode,
                                   self._ping_a_query_received_node,
                                   self._ping_a_found_node,
                                   self._ping_a_replacement_node,
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
                self._maintenance_mode = NORMAL_MODE
        elif self._maintenance_mode == NORMAL_MODE:
            for _ in range(len(self._maintenance_tasks)):
                # We try maintenance tasks till one of them actually does work
                # or we have tried them all (whatever happens first) We loop
                # in range because I'm going to modify self._maintenance_tasks
                task = self._maintenance_tasks.pop(0)
                self._maintenance_tasks.append(task)
                node_ = task()
                if node_:
                    queries_to_send = [self._get_maintenance_query(node_)]
                    # This task did do some work. We are done here!
                    break
        
        return (_MAINTENANCE_DELAY[self._maintenance_mode],
                queries_to_send, maintenance_lookup_target)

    def _ping_a_staled_rnode(self):
        # Don't have self._next_stale_maintenance_index lower than
        # lowest_bucket
        
        starting_index = self._next_stale_maintenance_index
        result = None
        while not result:
            # Find a non-empty bucket
            sbucket = self.table.get_sbucket(
                self._next_stale_maintenance_index)
            m_bucket = sbucket.main
            self._next_stale_maintenance_index = (
                self._next_stale_maintenance_index + 1) % (NUM_BUCKETS - 1)
            if m_bucket:
                rnode = m_bucket.get_stalest_rnode()
                if time.time() > rnode.last_seen + QUARANTINE_PERIOD:
                    result = rnode
            if self._next_stale_maintenance_index == starting_index:
                # No node to be pinged in the whole table.
                break
        return result

    def _ping_a_found_node(self):
        num_pings = 1
        if self.table.num_rnodes < MIN_RNODES_BOOTSTRAP:
            # Extra ping when bootstrapping
            num_pings += 1
        for _ in range(num_pings):
            node_ = self._found_nodes_queue.pop(0)
            if node_:
                logger.debug('pinging node found: %r', node_)
                return node_
        return

    def _ping_a_query_received_node(self):
        return self._query_received_queue.pop(0)

    def _ping_a_replacement_node(self):
        return self._replacement_queue.pop(0)
                                  
    def _get_maintenance_query(self, node_):
        if not node_.id: 
            # Bootstrap nodes don't have id
            return Query(self.find_closest_msg, node_)

        if random.choice((False, True)):
            # 50% chance to send find_node with my id as target
            return Query(self.find_closest_msg, node_)

        # 50% chance to send a find_node to fill up a non-full bucket
        target_log_distance = self.table.find_next_bucket_with_room_index(
            node_=node_)
        if target_log_distance:
            target = self.my_node.id.generate_close_id(target_log_distance)
            return Query(
                message.OutgoingFindNodeQuery(self.my_node.id, target),
                node_)
        else:
            # Every bucket is full. We send a ping instead.
            return Query(self.ping_msg, node_)
        
    def on_query_received(self, node_):
        '''
        Return None when nothing to do
        Return a list of queries when queries need to be sent (the queries
        will be sent out by the caller)
        '''
        log_distance = self.my_node.log_distance(node_)
        try:
            sbucket = self.table.get_sbucket(log_distance)
        except(IndexError):
            return # Got a query from myself. Just ignore it.

        m_bucket = sbucket.main
        r_bucket = sbucket.replacement
        rnode = m_bucket.get_rnode(node_)
        if rnode:
            # node in routing table: inform rnode
            self._update_rnode_on_query_received(rnode)
            return
        
        # node is not in the routing table
        if m_bucket.there_is_room():
            # There is room in the bucket: queue it
            self._query_received_queue.add(node_, log_distance)
            return
        # No room in the main routing table
        # Add to replacement table (if the bucket is not full)
        worst_rnode = self._worst_rnode(r_bucket.rnodes)
        if worst_rnode \
                and worst_rnode.timeouts_in_a_row() > MAX_NUM_TIMEOUTS:
            r_bucket.remove(worst_rnode)
            rnode = node_.get_rnode(log_distance)
            r_bucket.add(rnode)
            self._update_rnode_on_query_received(rnode)
        return
            
    def on_response_received(self, node_, rtt, nodes):
        if nodes:
            logger.debug('nodes found: %r', nodes)
        self._found_nodes_queue.add(nodes)

        logger.debug('on response received %f', rtt)
        log_distance = self.my_node.log_distance(node_)
        try:
            sbucket = self.table.get_sbucket(log_distance)
        except(IndexError):
            return # Got a response from myself. Just ignore it.
        m_bucket = sbucket.main
        r_bucket = sbucket.replacement
        rnode = m_bucket.get_rnode(node_)
        if rnode:
            # node in routing table: update
            self._update_rnode_on_response_received(rnode, rtt)
            return
        # The node is not in main
        rnode = r_bucket.get_rnode(node_)
        if rnode:
            # node in replacement table
            # let's see whether there is room in the main
            self._update_rnode_on_response_received(rnode, rtt)
            #TODO: leave this for the maintenance task
            if m_bucket.there_is_room():
                m_bucket.add(rnode)
                self.table.update_lowest_index(log_distance)
                self.table.num_rnodes += 1
                self._update_rnode_on_response_received(rnode, rtt)
                r_bucket.remove(rnode)
            return
        # The node is nowhere
        # Add to main table (if the bucket is not full)
        #TODO: check whether in replacement_mode
        if m_bucket.there_is_room():
            rnode = node_.get_rnode(log_distance)
            m_bucket.add(rnode)
            self.table.update_lowest_index(log_distance)
            self.table.num_rnodes += 1
            self._update_rnode_on_response_received(rnode, rtt)
            return
        # The main bucket is full
        # Let's see whether this node's latency is good
        current_time = time.time()
        rnode_to_be_replaced = None
        for rnode in reversed(m_bucket.rnodes):
            rnode_age = current_time - rnode.bucket_insertion_ts
            if rtt < rnode.rtt * (1 - (rnode_age / 7200)):
                # A rnode can only be replaced when the candidate node's RTT
                # is shorter by a factor. Over time, this factor
                # decreases. For instance, when rnode has been in the bucket
                # for 30 mins (1800 secs), a candidate's RTT must be at most
                # 50% of the rnode's RTT (ie. two times faster). After two
                # hours, a rnode cannot be replaced becouse of better RTT.
#                print 'RTT replacement: newRTT: %f, oldRTT: %f, age: %f' % (
#                rtt, rnode.rtt, current_time - rnode.bucket_insertion_ts)
                rnode_to_be_replaced = rnode
                break
        if rnode_to_be_replaced:
            m_bucket.remove(rnode_to_be_replaced)
            rnode = node_.get_rnode(log_distance)
            m_bucket.add(rnode)
            # No need to update table
            self.table.num_rnodes += 0
            self._update_rnode_on_response_received(rnode, rtt)
            return
            
        # Get the worst node in replacement bucket and see whether
        # it's bad enough to be replaced by node_
        worst_rnode = self._worst_rnode(r_bucket.rnodes)
        if worst_rnode \
                and worst_rnode.timeouts_in_a_row() > MAX_NUM_TIMEOUTS:
            # This node is better candidate than worst_rnode
            r_bucket.remove(worst_rnode)
            rnode = node_.get_rnode(log_distance)
            r_bucket.add(rnode)
            self._update_rnode_on_response_received(rnode, rtt)
        return
        
    def on_error_received(self, node_addr):
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
        r_bucket = sbucket.replacement
        rnode = m_bucket.get_rnode(node_)
        if rnode:
            # node in routing table: kick it out
            self._update_rnode_on_timeout(rnode)
            m_bucket.remove(rnode)
            self.table.update_lowest_index(log_distance)
            self.table.num_rnodes -= 1

            for r_rnode in r_bucket.sorted_by_rtt():
                self._replacement_queue.add(r_rnode)
            if r_bucket.there_is_room():
                r_bucket.add(rnode)
            else:
                worst_rnode = self._worst_rnode(r_bucket.rnodes)
                if worst_rnode:
                    # Replace worst node in replacement table
                    r_bucket.remove(worst_rnode)
                    r_bucket.add(rnode)
        # Node is not in main table
        rnode = r_bucket.get_rnode(node_)
        if rnode:
            # Node in replacement table: just update rnode
            self._update_rnode_on_timeout(rnode)
            
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
            rnode.in_quarantine = \
                rnode.last_action_ts < current_time - QUARANTINE_PERIOD
                
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

        
class _ReplacementQueue(object):

    def __init__(self, table):
        self.table = table
        self._queue = []

    def add(self, rnode):
        self._queue.append(rnode)

    def pop(self, _):
        while self._queue:
            rnode = self._queue.pop(0)
            log_distance = self.table.my_node.log_distance(rnode)
            sbucket = self.table.get_sbucket(log_distance)
            m_bucket = sbucket.main
            if m_bucket.there_is_room():
                # room in main: return it
                return rnode
        return

class _QueryReceivedQueue(object):

    def __init__(self, table):
        self.table = table
        self._queue = []
        self._queued_nodes_set = set()
        self._nodes_queued_per_bucket = [0 for _ in range(160)]

    def add(self, node_, log_distance):
        # The caller already checked that there is room in the bucket
#        print 'received queue', len(self._queue)
        if node_ in self._queued_nodes_set:
            # This node is already queued
            return
        num_nodes_queued = self._nodes_queued_per_bucket[log_distance]
        if num_nodes_queued >= 8:
            # many nodes queued for this bucket already
            return
        self._queued_nodes_set.add(node_)
        self._nodes_queued_per_bucket[log_distance] = (
            num_nodes_queued + 1)
        self._queue.append((time.time(), node_))

    def pop(self, _):
        while self._queue:
            ts, node_ = self._queue[0]
            time_in_queue = time.time() - ts
            if time_in_queue < QUARANTINE_PERIOD:
                return
            # Quarantine period passed
            log_distance = self.table.my_node.log_distance(node_)
            self._queued_nodes_set.remove(node_)
            self._nodes_queued_per_bucket[log_distance] = (
                self._nodes_queued_per_bucket[log_distance] - 1)
            del self._queue[0]
            sbucket = self.table.get_sbucket(log_distance)
            m_bucket = sbucket.main
            if m_bucket.there_is_room():
                # room in main: return it
                return node_
        return

class _FoundNodesQueue(object):

    def __init__(self, table):
        self.table = table
        self._queue = []
        self._queued_nodes_set = set()
        self._nodes_queued_per_bucket = [0 for _ in range(160)]

    def add(self, nodes):
#        print 'found queue', len(self._queue)
        for node_ in nodes:
            if node_ in self._queued_nodes_set:
                # This node has already been queued
                continue
            log_distance = self.table.my_node.log_distance(node_)
            num_nodes_queued = self._nodes_queued_per_bucket[log_distance]
            if num_nodes_queued >= 8:
                # many nodes queued for this bucket already
                continue
            try:
                sbucket = self.table.get_sbucket(log_distance)
            except(IndexError):
                continue # this node is myself (index == -1)
            m_bucket = sbucket.main
            rnode = m_bucket.get_rnode(node_)
            if not rnode and m_bucket.there_is_room():
                # Not in the main: add to the queue if there is room in main
                self._nodes_queued_per_bucket[log_distance] = (
                    num_nodes_queued + 1)
                self._queued_nodes_set.add(node_)
                self._queue.append(node_)

    def pop(self, _): 
        while self._queue:
            node_ = self._queue.pop(0)
            self._queued_nodes_set.remove(node_)
            log_distance = self.table.my_node.log_distance(node_)
            sbucket = self.table.get_sbucket(log_distance)
            m_bucket = sbucket.main
            rnode = m_bucket.get_rnode(node_)
            if not rnode and m_bucket.there_is_room():
                # Not in the main: return it if there is room in main
                return node_
        return

            
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
