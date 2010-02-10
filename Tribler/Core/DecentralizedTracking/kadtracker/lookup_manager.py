# Copyright (C) 2009 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

import sys
import threading

import logging

import identifier as identifier
import message as message


logger = logging.getLogger('dht')


MAX_PARALLEL_QUERIES = 16

ANNOUNCE_REDUNDANCY = 3

class _QueuedNode(object):

    def __init__(self, node_, log_distance):
        self.node = node_
        self.log_distance = log_distance
        self.queried = False

class _LookupQueue(object):

    def __init__(self, target_id, queue_size):
        self.target_id = target_id
        self.queue_size = queue_size
        self.queue = [_QueuedNode(None, identifier.ID_SIZE_BITS+1)]
        # Queued_ips is used to prevent that many Ids are
        # claimed from a single IP address.
        self.queued_ips = {}

    def add(self, nodes):
        for node_ in nodes:
            if node_.ip in self.queued_ips:
                continue # Already queued
            self.queued_ips[node_.ip] = None

            log_distance = self.target_id.log_distance(node_.id)
            for i, qnode in enumerate(self.queue):
                if log_distance < qnode.log_distance:
                    break
            self.queue = self.queue[:i] \
                + [_QueuedNode(node_, log_distance)] \
                + self.queue[i:self.queue_size-1]

    def pop_closest_node(self):
        """ Raise IndexError when empty queue"""
        for qnode in self.queue:
            if qnode.node and not qnode.queried:
                qnode.queried = True
                return qnode.node
        raise IndexError('No more nodes in the queue.')

   
class GetPeersLookup(object):
    """DO NOT use underscored variables, they are thread-unsafe.
    Variables without leading underscore are thread-safe.

    All nodes in bootstrap_nodes MUST have ID.
    """

    def __init__(self, my_id, querier_, max_parallel_queries,
                 info_hash, callback_f, bootstrap_nodes,
                 bt_port=None):
        logger.debug('New lookup (info_hash: %r)' % info_hash)
        self._my_id = my_id
        self._querier = querier_
        self._max_parallel_queries = max_parallel_queries
        self._get_peers_msg = message.OutgoingGetPeersQuery(
            my_id, info_hash)
        self._callback_f = callback_f
        self._lookup_queue = _LookupQueue(info_hash,
                                          max_parallel_queries * 2)
        self._lookup_queue.add(bootstrap_nodes)
        self._num_parallel_queries = 0

        self._info_hash = info_hash
        self._bt_port = bt_port
        self._lock = threading.RLock()

        self._announce_candidates = []
        self._num_responses_with_peers = 0
        self._is_done = False

    @property
    def is_done(self):
        #with self._lock:
        self._lock.acquire()
        try:
            is_done = self._is_done
        finally:
            self._lock.release()
        return is_done

    @property
    def num_parallel_queries(self):
        #with self._lock:
        self._lock.acquire()
        try:
            num_parallel_queries = self._num_parallel_queries
        finally:
            self._lock.release()
        return num_parallel_queries

    def start(self):
        self._send_queries()

        
    def _on_response(self, response_msg, node_):
        logger.debug('response from %r\n%r' % (node_,
                                                response_msg))
        #with self._lock:
        self._lock.acquire()
        try:
            self._num_parallel_queries -= 1
            try:
                peers = response_msg.peers
                logger.debug('PEERS\n%r' % peers)
                self._num_responses_with_peers += 1
                #TODO2: Halve queue size as well?
                # We've got some peers, let's back off a little
                self._max_parallel_queries = max(
                    self._max_parallel_queries / 2, 1)
                self._callback_f(peers)
            except (AttributeError):
                pass
            nodes = []
            try:
                nodes.extend(response_msg.nodes)
            except (AttributeError):
                pass
            try:
                nodes.extend(response_msg.nodes2)
            except (AttributeError):
                pass
            logger.info('NODES: %r' % (nodes))
            self._add_to_announce_candidates(node_,
                                             response_msg.token)
            self._lookup_queue.add(nodes)
            self._send_queries()
        finally:
            self._lock.release()

    def _on_timeout(self, node_):
        logger.debug('TIMEOUT node: %r' % node_)
        #with self._lock:
        self._lock.acquire()
        try:
            self._num_parallel_queries -= 1
            self._send_queries()
        finally:
            self._lock.release()

    def _on_error(self, error_msg, node_): 
        logger.debug('ERROR node: %r' % node_)
        #with self._lock:
        self._lock.acquire()
        try:
            self._num_parallel_queries -= 1
            self._send_queries()
        finally:
            self._lock.release()

    def _send_queries(self):
        #with self._lock:
        self._lock.acquire()
        try:
            while self._num_parallel_queries < self._max_parallel_queries:
                try:
                    node_ = self._lookup_queue.pop_closest_node()
                    logger.debug('popped node %r' % node_)
                except(IndexError):
                    logger.debug('no more candidate nodes!')
                    if not self._num_parallel_queries:
                        logger.debug('Lookup DONE')
                        self._announce()
                    return
                if node_.id == self._my_id:
                    # Don't send to myself
                    continue
                self._num_parallel_queries += 1
                logger.debug('sending to: %r, parallelism: %d/%d' %
                    (node_,
                     self._num_parallel_queries,
                     self._max_parallel_queries))
                self._querier.send_query(self._get_peers_msg, node_,
                                         self._on_response,
                                        self._on_timeout,
                                        self._on_error)
        finally:
            self._lock.release()

    def _add_to_announce_candidates(self, node_, token):
        node_log_distance = node_.id.log_distance(self._info_hash)
        self._announce_candidates.append((node_log_distance,
                                          node_,
                                          token))
        for i in xrange(len(self._announce_candidates)-1, 0, -1):
            if self._announce_candidates[i][1] \
                    < self._announce_candidates[i-1][1]:
                tmp1, tmp2 =  self._announce_candidates[i-1:i+1] 
                self._announce_candidates[i-1:i+1] = tmp2, tmp1
            else:
                break
        self._announce_candidates = \
            self._announce_candidates[:ANNOUNCE_REDUNDANCY]

    def _do_nothing(self, *args, **kwargs):
        #TODO2: generate logs
        pass

    def _announce(self):
        self._is_done = True
        if not self._bt_port:
            return
        for (_, node_, token) in self._announce_candidates:
            logger.debug('announcing to %r' % node_)
            msg = message.OutgoingAnnouncePeerQuery(
                self._my_id, self._info_hash, self._bt_port, token)
            self._querier.send_query(msg, node_,
                                     self._do_nothing,
                                     self._do_nothing,
                                     self._do_nothing)


    def _get_announce_candidates(self):
        return [e[1] for e in self._announce_candidates]
    
        
class LookupManager(object):

    def __init__(self, my_id, querier_, routing_m,
                 max_parallel_queries=MAX_PARALLEL_QUERIES):
        self.my_id = my_id
        self.querier = querier_
        self.routing_m = routing_m
        self.max_parallel_queries = max_parallel_queries


    def get_peers(self, info_hash, callback_f, bt_port=None):
        lookup_q = GetPeersLookup(
            self.my_id, self.querier,
            self.max_parallel_queries, info_hash, callback_f,
            self.routing_m.get_closest_rnodes(info_hash),
            bt_port)
        lookup_q.start()
        return lookup_q

    def stop(self):
        self.querier.stop()


#TODO2: During the lookup, routing_m gets nodes_found and sends find_node
        # to them (in addition to the get_peers sent by lookup_m)
