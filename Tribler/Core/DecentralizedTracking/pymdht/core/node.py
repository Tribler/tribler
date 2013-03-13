# Copyright (C) 2009-2010 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

import ptime as time

import utils
import identifier

class Node(object):

    def __init__(self, addr, node_id=None, version=1, ns_node=False):
        #assert version != 1 # debug only
        self._addr = addr
        self._id = node_id
        self.version = version
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

    @property
    def ip(self):
        return self._addr[0]

    def __eq__(self, other):
        if self.addr == other.addr:
            try:
                return self.id == other.id
            except AttributeError: #self.id == None (id.bin_id fails)
                return self.id is None and other.id is None
        else:
            return False

    def __ne__(self, other):
        return not self == other

    def __hash__(self):
        if self.id:
            return self.addr.__hash__() ^ self.id.__hash__()
        else:
            return self.addr.__hash__()

    def __repr__(self):
        return '<node: %26r %r (%s)>' % (self.addr,
                                       self.id,
                                       self.version)

    def distance(self, other):
        return self.id.distance(other.id)

    def log_distance(self, other):
        # Only for backward compatibility. It will be removed.
        return self.distance(other).log

    def compact(self):
        """Return compact format"""
        return self.id.bin_id + self.compact_addr

    def get_rnode(self, log_distance):
        return RoutingNode(self, log_distance)

QUERY = 'query'
RESPONSE = 'response'
TIMEOUT = 'timeout'

MAX_LAST_EVENTS = 10

class RoutingNode(Node):

    def __init__(self, node_, log_distance):
        Node.__init__(self, node_.addr, node_.id, node_.version,
                      node_.is_ns)
        self.log_distance_to_me = log_distance
        self.rtt = 99
        self.real_rtt = 99
        self.rtt_avg = None
        self.num_queries = 0
        self.num_responses = 0
        self.num_timeouts = 0
        self.msgs_since_timeout = 0
        self.last_events = []
        #self.refresh_task = None
        self.rank = 0
        current_time = time.time()
        self.creation_ts = current_time
        self.last_action_ts = current_time
        self.in_quarantine = True
        self.last_seen = current_time
        self.bucket_insertion_ts = None

    #def __repr__(self):
    #    return '<rnode: %r %r>' % (self.addr, self.id)

    def get_rnode(self):
        return self

    def get_node(self):
        return Node(self.addr, self.id)

    def add_event(self, timestamp, event):
        self.last_events.append((timestamp, event))
        self.last_events = self.last_events[:MAX_LAST_EVENTS]

    def timeouts_in_a_row(self, consider_queries=True):
        """Return number of timeouts in a row for this rnode."""
        result = 0
        for timestamp, event in reversed(self.last_events):
            if event == TIMEOUT:
                result += 1
            elif event == RESPONSE or \
                     (consider_queries and event == QUERY):
                return result
        return result # all timeouts (and queries), or empty list


class LookupNode(Node):

    def __init__(self, node_, target):
        Node.__init__(self, node_.addr, node_.id, node_.version,
                      node_.is_ns)
        self.node = node_
        self.target = target
        self.distance_to_target = self.id.distance(target)
