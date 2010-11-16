# Copyright (C) 2009-2010 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

import sys
import threading
import mdht.ptime as time

import logging

from mdht.querier import Query
import mdht.identifier as identifier
import mdht.message as message


logger = logging.getLogger('dht')

MARK_INDEX = 2

ANNOUNCE_REDUNDANCY = 3

class _QueuedNode(object):

    def __init__(self, node_, log_distance, token):
        self.node = node_
        self.log_distance = log_distance
        self.token = token

    def __cmp__(self, other):
        return self.log_distance - other.log_distance

class _LookupQueue(object):

    def __init__(self, info_hash, queue_size):
        self.info_hash = info_hash
        self.queue_size = queue_size
        self.queue = [_QueuedNode(None, identifier.ID_SIZE_BITS+1, None)]
        # *_ips is used to prevent that many Ids are
        # claimed from a single IP address.
        self.queued_ips = set()
        self.queried_ips = set()
        self.queued_qnodes = []
        self.responded_qnodes = []
        self.max_queued_qnodes = 16
        self.max_responded_qnodes = 16

        self.last_query_ts = time.time()

    def bootstrap(self, rnodes, max_nodes):
        # Assume that the ips are not duplicated.
        qnodes = [_QueuedNode(n, n.id.log_distance(
                    self.info_hash), None)
                  for n in rnodes]
        self._add_queued_qnodes(qnodes)
        return self._pop_nodes_to_query(max_nodes)

    def on_response(self, src_node, nodes, token, max_nodes):
        ''' Nodes must not be duplicated'''
        qnode = _QueuedNode(src_node,
                            src_node.id.log_distance(self.info_hash),
                            token)
        self._add_responded_qnode(qnode)
        qnodes = [_QueuedNode(n, n.id.log_distance(
                    self.info_hash), None)
                  for n in nodes]
        self._add_queued_qnodes(qnodes)
        return self._pop_nodes_to_query(max_nodes)

    def on_timeout(self, src_node, max_nodes):
        return self._pop_nodes_to_query(max_nodes)

    on_error = on_timeout
    
    def get_closest_responded_qnodes(self,
                                     num_nodes=ANNOUNCE_REDUNDANCY):
        closest_responded_qnodes = []
        for qnode in self.responded_qnodes:
            if qnode.token:
                closest_responded_qnodes.append(qnode)
                if len(closest_responded_qnodes) == num_nodes:
                    break
        return closest_responded_qnodes

    def _add_queried_ip(self, ip):
        if ip not in self.queried_ips:
            self.queried_ips.add(ip)
            return True
        
    def _add_responded_qnode(self, qnode):
        self.responded_qnodes.append(qnode)
        self.responded_qnodes.sort()
        del self.responded_qnodes[self.max_responded_qnodes:]

    def _add_queued_qnodes(self, qnodes):
        for qnode in qnodes:
#            print 'adding qnode', qnode
            if qnode.node.ip not in self.queued_ips \
                    and qnode.node.ip not in self.queried_ips:
                self.queued_qnodes.append(qnode)
                self.queued_ips.add(qnode.node.ip)
        self.queued_qnodes.sort()
        for qnode  in self.queued_qnodes[self.max_queued_qnodes:]:
            self.queued_ips.remove(qnode.node.ip)
        del self.queued_qnodes[self.max_queued_qnodes:]

    def _pop_nodes_to_query(self, max_nodes):
        if len(self.responded_qnodes) > MARK_INDEX:
            mark = self.responded_qnodes[MARK_INDEX].log_distance
        else:
            mark = identifier.ID_SIZE_BITS
        nodes_to_query = [] 
        for _ in range(max_nodes):
            try:
                qnode = self.queued_qnodes[0]
            except (IndexError):
                break # no more queued nodes left
            if qnode.log_distance < mark:
                self.queried_ips.add(qnode.node.ip)
                nodes_to_query.append(qnode.node)
                del self.queued_qnodes[0]
                self.queued_ips.remove(qnode.node.ip)
        self.last_query_ts = time.time()
        return nodes_to_query

   
class GetPeersLookup(object):
    """DO NOT use underscored variables, they are thread-unsafe.
    Variables without leading underscore are thread-safe.

    All nodes in bootstrap_nodes MUST have ID.
    """

    def __init__(self, my_id,
                 info_hash, callback_f,
                 bt_port=None):
        self.bootstrap_alpha = 16
        self.normal_alpha = 999
        self.normal_m = 3
        self.slowdown_alpha = 999
        self.slowdown_m = 2
        logger.debug('New lookup (info_hash: %r)' % info_hash)
        self._my_id = my_id
        self._get_peers_msg = message.OutgoingGetPeersQuery(
            my_id, info_hash)
        self.callback_f = callback_f
        self._lookup_queue = _LookupQueue(info_hash, 20)
                                     
        self._info_hash = info_hash
        self._bt_port = bt_port
        self._lock = threading.RLock()

        self._num_parallel_queries = 0

        self.num_queries = 0
        self.num_responses = 0
        self.num_timeouts = 0
        self.num_errors = 0

        self._running = False
        self._slow_down = False

    def _get_max_nodes_to_query(self):
        if self._slow_down:
            return min(self.slowdown_alpha - self._num_parallel_queries,
                       self.slowdown_m)
        return min(self.normal_alpha - self._num_parallel_queries,
                   self.normal_m)
    
    def start(self, bootstrap_rnodes):
        assert not self._running
        self._running = True
        nodes_to_query = self._lookup_queue.bootstrap(bootstrap_rnodes,
                                                      self.bootstrap_alpha)
        queries_to_send = self._get_lookup_queries(nodes_to_query)
        return queries_to_send
        
    def on_response_received(self, response_msg, node_):
        logger.debug('response from %r\n%r' % (node_,
                                                response_msg))
        self._num_parallel_queries -= 1
        self.num_responses += 1
        token = getattr(response_msg, 'token', None)
        peers = getattr(response_msg, 'peers', None)
        if peers:
            self._slow_down = True

        max_nodes = self._get_max_nodes_to_query()
        nodes_to_query = self._lookup_queue.on_response(node_,
                                                        response_msg.all_nodes,
                                                        token, max_nodes)
        queries_to_send = self._get_lookup_queries(nodes_to_query)
        return (queries_to_send, peers, self._num_parallel_queries,
                not self._num_parallel_queries)

    def on_timeout(self, node_):
        logger.debug('TIMEOUT node: %r' % node_)
        self._num_parallel_queries -= 1
        self.num_timeouts += 1
        self._slow_down = True

        max_nodes = self._get_max_nodes_to_query()
        nodes_to_query = self._lookup_queue.on_timeout(node_, max_nodes)
        queries_to_send = self._get_lookup_queries(nodes_to_query)
        return (queries_to_send, self._num_parallel_queries,
                not self._num_parallel_queries)
    
    def on_error(self, error_msg, node_):
        logger.debug('ERROR node: %r' % node_)
        self._num_parallel_queries -= 1
        self.num_errors += 1

        max_nodes = self._get_max_nodes_to_query()
        nodes_to_query = self._lookup_queue.on_error(node_, max_nodes)
        queries_to_send = self._get_lookup_queries(nodes_to_query)
        return (queries_to_send, self._num_parallel_queries,
                not self._num_parallel_queries)
        
    def _get_lookup_queries(self, nodes):
        queries = []
        for node_ in nodes:
            if node_.id == self._my_id:
                # Don't send to myself
                continue
            self._num_parallel_queries += 1
            self.num_queries += len(nodes)
            queries.append(Query(self._get_peers_msg, node_, self))
        return queries
'''
    def _announce(self):
        if not self._bt_port:
            return
        queries_to_send = []
        for qnode in self._lookup_queue.get_closest_responded_qnodes():
            logger.debug('announcing to %r' % qnode.node)
            msg = message.OutgoingAnnouncePeerQuery(
                self._my_id, self._info_hash, self._bt_port, qnode.token)
            queries_to_send.append((msg, qnode.node))
        return  queries_to_send
'''
            
class MaintenanceLookup(GetPeersLookup):

    def __init__(self, my_id, target):
        GetPeersLookup.__init__(self, my_id, target, None)
        self.bootstrap_alpha = 4
        self.normal_alpha = 4
        self.normal_m = 1
        self.slowdown_alpha = 4
        self.slowdown_m = 1
        self._get_peers_msg = message.OutgoingFindNodeQuery(my_id,
                                                            target)
            
        
class LookupManager(object):

    def __init__(self, my_id):
        self.my_id = my_id

    def get_peers(self, info_hash, callback_f, bt_port=None):
        lookup_q = GetPeersLookup(self.my_id, info_hash,
                                  callback_f, bt_port)
        return lookup_q

    def maintenance_lookup(self, target=None):
        target = target or self.my_id
        lookup_q = MaintenanceLookup(self.my_id, target)
        return lookup_q
