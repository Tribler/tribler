# Copyright (C) 2009-2010 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

import ptime as time
import os
import cPickle

import logging, logging_conf

import identifier
from identifier import Id
import message
import token_manager
import tracker
from minitwisted import ThreadedReactor

from querier import Querier
#from responder import Responder
from message import QUERY, RESPONSE, ERROR, OutgoingGetPeersQuery
from node import Node

#from profilestats import profile

logger = logging.getLogger('dht')

SAVE_STATE_DELAY = 1 * 60
STATE_FILENAME = 'state.dat'


TIMEOUT_DELAY = 2

NUM_NODES = 8

class Controller:

    def __init__(self, dht_addr, state_path, routing_m_mod, lookup_m_mod):
        self.state_filename = os.path.join(state_path, STATE_FILENAME)
        self.load_state()
        if not self._my_id:
            self._my_id = identifier.RandomId()
        self._my_node = Node(dht_addr, self._my_id)
        self._tracker = tracker.Tracker()
        self._token_m = token_manager.TokenManager()

        self._reactor = ThreadedReactor()
        self._reactor.listen_udp(self._my_node.addr[1],
                                 self._on_datagram_received)
        #self._rpc_m = RPCManager(self._reactor)
        self._querier = Querier(self._my_id)
        bootstrap_nodes = self.loaded_nodes or BOOTSTRAP_NODES
        del self.loaded_nodes
        self._routing_m = routing_m_mod.RoutingManager(self._my_node, 
                                                       bootstrap_nodes)
#        self._responder = Responder(self._my_id, self._routing_m,
#                                    self._tracker, self._token_m)

        self._lookup_m = lookup_m_mod.LookupManager(self._my_id)
        current_time = time.time()
        self._next_maintenance_ts = current_time
        self._next_save_state_ts = current_time + SAVE_STATE_DELAY
        
        self._running = False
        

    def start(self):
        assert not self._running
        self._running = True
        self._reactor.start()
        self._main_loop()

    def stop(self):
        assert self._running
        #TODO2: stop each manager
        self._reactor.stop()

    def save_state(self):
        rnodes = self._routing_m.get_main_rnodes()
        f = open(self.state_filename, 'w')
        f.write('%r\n' % self._my_id)
        for rnode in rnodes:
            f.write('%d\t%r\t%s\t%d\t%f\n' % (
                    self._my_id.log_distance(rnode.id),
                    rnode.id, rnode.addr[0], rnode.addr[1],
                    rnode.rtt * 1000))
        f.close()

    def load_state(self):
        self._my_id = None
        self.loaded_nodes = []
        try:
            f = open(self.state_filename)
        except(IOError):
            return
        # the first line contains this node's identifier
        hex_id = f.readline().strip()
        self._my_id = Id(hex_id)
        # the rest of the lines contain routing table nodes
        # FORMAT
        # log_distance hex_id ip port rtt
        for line in f:
            _, hex_id, ip, port, _ = line.split()
            addr = (ip, int(port))
            node_ = Node(addr, Id(hex_id))
            self.loaded_nodes.append(node_)
        f.close
        
    def get_peers(self, lookup_id, info_hash, callback_f, bt_port=0):
        logger.critical('get_peers %d %r' % (bt_port, info_hash))
        assert self._running
        # look if I'm tracking this info_hash
        peers = self._tracker.get(info_hash)
        if peers:
            callback_f(lookup_id, peers)
        # do the lookup
        log_distance = info_hash.log_distance(self._my_id)
        bootstrap_rnodes = self._routing_m.get_closest_rnodes(log_distance,
                                                              None,
                                                              True)
        lookup_obj = self._lookup_m.get_peers(info_hash, callback_f, bt_port)
        #TODO: propagate lookup_id to the lookup plugin
        lookup_obj.lookup_id = lookup_id
        ################################################
        lookup_queries_to_send = lookup_obj.start(bootstrap_rnodes)
        self._send_queries(lookup_queries_to_send)
        return len(lookup_queries_to_send)
        
    def print_routing_table_stats(self):
        self._routing_m.print_stats()

    def _main_loop(self):
        current_time = time.time()
        # Routing table
        if current_time > self._next_maintenance_ts:
            (maintenance_delay,
             queries_to_send,
             maintenance_lookup_target) = self._routing_m.do_maintenance()
            self._send_queries(queries_to_send)
            if maintenance_lookup_target:
                log_distance = maintenance_lookup_target.log_distance(
                    self._my_id)
                bootstrap_nodes = self._routing_m.get_closest_rnodes(
                    log_distance, None, True)
                lookup_obj = self._lookup_m.maintenance_lookup(
                    maintenance_lookup_target)
                lookup_queries_to_send = lookup_obj.start(bootstrap_nodes)
                self._send_queries(lookup_queries_to_send)
            self._next_maintenance_ts = (current_time
                                         + maintenance_delay)
        # Auto-save routing table
        if current_time > self._next_save_state_ts:
            self.save_state()
            self._next_save_state_ts = current_time + SAVE_STATE_DELAY

        # Schedule next call
        delay = (min(self._next_maintenance_ts, self._next_save_state_ts)
                 - current_time)
        self._reactor.call_later(delay, self._main_loop)

    def _maintenance_lookup(self, target):
        self._lookup_m.maintenance_lookup(target)

    def _on_datagram_received(self, data, addr):
        try:
            msg = message.IncomingMsg(data, addr)
        except(message.MsgError):
            return # ignore message
        
        if msg.type == message.QUERY:
            response_msg = self._get_response(msg)
            if response_msg:
                bencoded_response = response_msg.encode(msg.tid)
                self._reactor.sendto(bencoded_response, addr)

            maintenance_queries_to_send = self._routing_m.on_query_received(
                msg.sender_node)
            
        elif msg.type in (message.RESPONSE, message.ERROR):
            related_query = self._querier.on_response_received(msg, addr)
            if not related_query:
                # Query timed out or unrequested response
                return
            # lookup related tasks
            if related_query.lookup_obj:
                if msg.type == message.RESPONSE:
                    (lookup_queries_to_send,
                     peers,
                     num_parallel_queries,
                     lookup_done
                     ) = related_query.lookup_obj.on_response_received(
                        msg, msg.sender_node)
                else: #ERROR
                    peers = None # an error msg doesn't have peers
                    (lookup_queries_to_send,
                     num_parallel_queries,
                     lookup_done
                     ) = related_query.lookup_obj.on_error_received(
                        msg, msg.sender_node)
                self._send_queries(lookup_queries_to_send)
                
                if related_query.lookup_obj.callback_f:
                    
                    lookup_id = related_query.lookup_obj.lookup_id
                    if peers:
                        related_query.lookup_obj.callback_f(lookup_id, peers)
                    if lookup_done:
                        queries_to_send = related_query.lookup_obj.announce()
                        self._send_queries(queries_to_send)
                        related_query.lookup_obj.callback_f(lookup_id, None)
            # maintenance related tasks
            if msg.type == message.RESPONSE:
                maintenance_queries_to_send = \
                    self._routing_m.on_response_received(
                    msg.sender_node, related_query.rtt, msg.all_nodes)
            else:
                maintenance_queries_to_send = \
                    self._routing_m.on_error_received(
                    msg.sender_node)
        else: # unknown type
            return
        self._send_queries(maintenance_queries_to_send)

    def _get_response(self, msg):
        if msg.query == message.PING:
            return message.OutgoingPingResponse(self._my_id)
        elif msg.query == message.FIND_NODE:
            log_distance = msg.target.log_distance(self._my_id)
            rnodes = self._routing_m.get_closest_rnodes(log_distance,
                                                       NUM_NODES, False)
            return message.OutgoingFindNodeResponse(self._my_id,
                                                    rnodes)
        elif msg.query == message.GET_PEERS:
            token = self._token_m.get()
            log_distance = msg.info_hash.log_distance(self._my_id)
            rnodes = self._routing_m.get_closest_rnodes(log_distance,
                                                       NUM_NODES, False)
            peers = self._tracker.get(msg.info_hash)
            if peers:
                logger.debug('RESPONDING with PEERS:\n%r' % peers)
            return message.OutgoingGetPeersResponse(self._my_id,
                                                    token,
                                                    nodes=rnodes,
                                                    peers=peers)
        elif msg.query == message.ANNOUNCE_PEER:
            peer_addr = (msg.sender_addr[0], msg.bt_port)
            self._tracker.put(msg.info_hash, peer_addr)
            return message.OutgoingAnnouncePeerResponse(self._my_id)
        else:
            logger.debug('Invalid QUERY: %r' % (msg.query))
            #TODO: maybe send an error back?
        
    def _on_response_received(self, msg):
        pass

    def _on_timeout(self, addr):
        related_query = self._querier.on_timeout(addr)
        if not related_query:
            return # timeout cancelled (got response/error already)
        if related_query.lookup_obj:
            (lookup_queries_to_send,
             num_parallel_queries,
             lookup_done
             ) = related_query.lookup_obj.on_timeout(related_query.dstnode)
            self._send_queries(lookup_queries_to_send)
            if lookup_done and related_query.lookup_obj.callback_f:
                queries_to_send = related_query.lookup_obj.announce()
                self._send_queries(queries_to_send)
                lookup_id = related_query.lookup_obj.lookup_id
                related_query.lookup_obj.callback_f(lookup_id, None)
        maintenance_queries_to_send = self._routing_m.on_timeout(
            related_query.dstnode)
        self._send_queries(maintenance_queries_to_send)

    def _send_queries(self, queries_to_send, lookup_obj=None):
        if queries_to_send is None:
            return
        for query in queries_to_send:
            timeout_task = self._reactor.call_later(TIMEOUT_DELAY,
                                                    self._on_timeout,
                                                    query.dstnode.addr)
            bencoded_query = self._querier.register_query(query, timeout_task)
            self._reactor.sendto(bencoded_query, query.dstnode.addr)

            
        
BOOTSTRAP_NODES = (
    Node(('67.215.242.138', 6881)), #router.bittorrent.com
    Node(('192.16.127.98', 7005)), #KTH node
    )
