# Copyright (C) 2009 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

import time

import utils
import identifier

class Node(object):

    def __init__(self, addr, node_id=None, ns_node=False):
        self._addr = addr
        self._id = node_id
        self.is_ns = ns_node
        self._compact_addr = utils.compact_addr(addr)

    def get_id(self):
        return self._id
    def set_id(self, node_id):
        if self._id is None:
            self._id = node_id
        else:
            raise AttributeError, "Node's id is read-only"
    id = property(get_id, set_id)

    @property
    def addr(self):
        return self._addr

    @property
    def compact_addr(self):
        return self._compact_addr

    def __eq__(self, other):
        try:
            return self.addr == other.addr and self.id == other.id
        except AttributeError: #self.id == None
            return self.id is None and other.id is None \
                   and self.addr == other.addr

    def __ne__(self, other):
        return not self == other

    def __repr__(self):
        return '<node: %r %r>' % (self.addr, self.id)

    def log_distance(self, other):
        return self.id.log_distance(other.id)

    def compact(self):
        """Return compact format"""
        return self.id.bin_id + self.compact_addr

    def get_rnode(self):
        return RoutingNode(self)
    


QUERY = 'query'
REPLY = 'reply'
TIMEOUT = 'timeout'

LAST_RTT_W = 0.2 # The weight of the last RTT to calculate average

MAX_NUM_TIMEOUT_STRIKES = 2
QUARANTINE_PERIOD = 3 * 60 # 3 minutes


class RoutingNode(Node):

    def __init__(self, node_):
        Node.__init__(self, node_.addr, node_.id, node_.is_ns)
        self._rtt_avg = None
        self._num_queries = 0
        self._num_responses = 0
        self._num_timeouts = 0
        self._msgs_since_timeout = 0
        self._last_events = []
        self._max_last_events = 10
        self.refresh_task = None
        self._rank = 0
        current_time = time.time()
        self._creation_ts = current_time
        self._last_action_ts = current_time
        self.in_quarantine = True
        
    def __repr__(self):
        return '<rnode: %r %r>' % (self.addr, self.id)

    def get_rnode(self):
        return self
    
    def on_query_received(self):
        """Register a query from node.

        You should call this method when receiving a query from this node.

        """
        self._last_action_ts = time.time()
        self._msgs_since_timeout += 1
        self._num_queries += 1
        self._last_events.append((time.time(), QUERY))
        self._last_events[:self._max_last_events]

    def on_response_received(self, rtt=0):
        """Register a reply from rnode.

        You should call this method when receiving a response from this rnode.

        """
        current_time = time.time()
        #self._reset_refresh_task()
        if self.in_quarantine:
            self.in_quarantine = \
                self._last_action_ts < current_time - QUARANTINE_PERIOD
                
        self._last_action_ts = current_time
        self._msgs_since_timeout += 1
        try:
            self._rtt_avg = \
                self._rtt_avg * (1 - LAST_RTT_W) + rtt * LAST_RTT_W
        except TypeError: # rtt_avg is None
            self._rtt_avg = rtt
        self._num_responses += 1
        self._last_events.append((time.time(), REPLY))
        self._last_events[:self._max_last_events]

    def on_timeout(self):
        """Register a timeout for this rnode.

        You should call this method when getting a timeout for this node.

        """
        self._last_action_ts = time.time()
        self._msgs_since_timeout = 0
        self._num_timeouts += 1
        self._last_events.append((time.time(), TIMEOUT))
        self._last_events[:self._max_last_events]

    def timeouts_in_a_row(self, consider_queries=True):
        """Return number of timeouts in a row for this rnode."""
        result = 0
        for timestamp, event in reversed(self._last_events):
            if event == TIMEOUT:
                result += 1
            elif event == REPLY or \
                     (consider_queries and event == QUERY):
                return result
        return result # all timeouts (and queries), or empty list
            
#     def rank(self):
#         if self._num_responses == 0:
#             # No responses received, the node might be unreachable
#             return 0
#         if self.timeouts_in_a_row() > MAX_NUM_TIMEOUT_STRIKES:
#             return 0
#         return self._num_queries + self._num_responses + \
#             -3 * self._num_timeouts

    
