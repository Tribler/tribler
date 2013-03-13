# Copyright (C) 2009-2010 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

import ptime as time
import logging

logger = logging.getLogger('dht')


class SuperBucket(object):
    def __init__(self, index, max_nodes, ips_in_main,
                 ips_in_replacement):
        self.index = index
        self.main = Bucket(max_nodes, ips_in_main)
        self.replacement = Bucket(max_nodes, ips_in_replacement)
        self.ips_in_main = ips_in_main
        self.ips_in_replacement = ips_in_replacement


class Bucket(object):
    def __init__(self, max_rnodes, ips_in_table):
        self.max_rnodes = max_rnodes
        self.ips_in_table = ips_in_table
        self.rnodes = []
        self.last_maintenance_ts = time.time()
        self.last_changed_ts = 0

    def get_rnode(self, node_):
        i = self._find(node_)
        if i >= 0:
            return self.rnodes[i]
        # return None when node is not found

    def add(self, rnode):
        assert len(self.rnodes) < self.max_rnodes
        rnode.bucket_insertion_ts = time.time()
        self.rnodes.append(rnode)
        if self.ips_in_table is not None:
            self.ips_in_table.add(rnode.ip)
        #self.last_changed_ts = time.time()

    def remove(self, node_):
        i = self._find(node_)
        assert 0 <= i < len(self.rnodes)
        assert self.rnodes[i].ip == node_.ip
        del self.rnodes[i]
        if self.ips_in_table is not None:
            self.ips_in_table.remove(node_.ip)

    def __repr__(self):
        return '\n'.join(['b>'] + [repr(rnode) for rnode in self.rnodes])

    def __len__(self):
        return len(self.rnodes)

    def __eq__(self, other):
        if self.max_rnodes != other.max_rnodes or len(self) != len(other):
            return False
        for self_rnode, other_rnode in zip(self.rnodes, other.rnodes):
            if self_rnode != other_rnode:
                return False
        return True

    def __ne__(self, other):
        return not self == other

    def there_is_room(self, min_places=1):
        return len(self.rnodes) + min_places <=  self.max_rnodes

#    def occupancy(self):
#        return float(len(self.rnodes) / self.max_rnodes)

    def get_freshest_rnode(self):
        freshest_ts = 0
        freshest_rnode = None
        for rnode in self.rnodes:
            if rnode.last_seen > freshest_ts:
                freshest_ts = rnode.last_seen
                freshest_rnode = rnode
        return freshest_rnode

    def get_stalest_rnode(self):
        oldest_ts = time.time()
        stalest_rnode = None
        for rnode in self.rnodes:
            if rnode.last_seen < oldest_ts:
                oldest_ts = rnode.last_seen
                stalest_rnode = rnode
        return stalest_rnode

    def sorted_by_rtt(self):
        return sorted(self.rnodes, key=lambda x: x.rtt)

#     def get_highest_rtt_rnode(self, num_stable_rnodes_to_ignore):
#         highest_rtt = 0
#         highest_rtt_rnode = None
#         if num_stable_rnodes_to_ignore:
#             rnodes = sorted(
#                 self.rnodes,
#                 lambda x,y: int(x.bucket_insertion_ts - y.bucket_insertion_ts))
#             nostable_rnodes = rnodes[num_stable_rnodes_to_ignore:]
#         else:
#             nostable_rnodes = self.rnodes
#         for rnode in nostable_rnodes:
#             if rnode.rtt > highest_rtt:
#                 highest_rtt = rnode.rtt
#                 highest_rtt_rnode = rnode
#         return highest_rtt_rnode

    def _find(self, node_):
        for i, rnode in enumerate(self.rnodes):
            if rnode == node_:
                return i
        return -1 # not found



NUM_SBUCKETS = 160 # log_distance returns a number in range [-1,159]
NUM_NODES = 8
class RoutingTable(object):
    '''
    '''

    def __init__(self, my_node, nodes_per_bucket):
        assert len(nodes_per_bucket) == NUM_SBUCKETS
        self.my_node = my_node
        self.nodes_per_bucket = nodes_per_bucket
        self.sbuckets = [None] * NUM_SBUCKETS
        self.num_rnodes = 0
        self._ips_in_main = set()
        self._ips_in_replacement = None #set() #bugfix
        return

    def get_sbucket(self, log_distance):
        index = log_distance
        if index < 0:
            raise IndexError, 'index (%d) must be >= 0' % index
        sbucket = self.sbuckets[index]
        if not sbucket:
            sbucket = SuperBucket(index, self.nodes_per_bucket[index],
                                  self._ips_in_main,
                                  self._ips_in_replacement)
            self.sbuckets[index] = sbucket
        return sbucket

    def get_closest_rnodes(self, log_distance, max_rnodes, exclude_myself):
        result = []
        index = log_distance
        for i in range(index, 0, -1):
            sbucket = self.sbuckets[i]
            if not sbucket:
                continue
            result.extend(sbucket.main.rnodes[:max_rnodes-len(result)])
            if len(result) == max_rnodes:
                return result
        # Include myself (when appropiate)
        if not exclude_myself:
            result.append(self.my_node)
        # If that wasn't enough we'll provide more (farther away) nodes
        for i in range(index + 1, NUM_SBUCKETS):
            sbucket = self.sbuckets[i]
            if not sbucket:
                continue
            result.extend(sbucket.main.rnodes[:max_rnodes-len(result)])
            if len(result) == max_rnodes:
                break
        return result

    def find_next_bucket_with_room_index(self, node_=None, log_distance=None):
        index = log_distance or node_.distance(self.my_node).log
        for i in range(index + 1, NUM_SBUCKETS):
            # exclude node's bucket
            sbucket = self.sbuckets[i]
            if sbucket is None or self.sbuckets[i].main.there_is_room():
                return i
        # return None when all buckets are full

    def get_main_rnodes(self):
        rnodes = []
        for i in range(0, NUM_SBUCKETS):
            sbucket = self.sbuckets[i]
            if sbucket:
                rnodes.extend(sbucket.main.rnodes)
        return rnodes

    def print_stats(self):
        num_nodes = 0
        for i, sbucket in enumerate(self.sbuckets):
            if sbucket and len(sbucket.main):
                print i, len(sbucket.main), len(sbucket.replacement)
        print 'Total:', self.num_rnodes

    def __repr__(self):
        begin = ['==============RoutingTable============= BEGIN']
        data = ['%d %r' % (i, sbucket)
                for i, sbucket in enumerate(self.sbuckets)]

        end = ['==============RoutingTable============= END']
        return '\n'.join(begin + data + end)
