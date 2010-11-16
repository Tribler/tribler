# Copyright (C) 2009 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

import time

import logging, logging_conf

import identifier
import message
import token_manager
import tracker
from routing_manager import RoutingManager
from minitwisted import ThreadedReactor
from rpc_manager import RPCManager
from querier import Querier
from responder import Responder
from message import QUERY, RESPONSE, ERROR, OutgoingGetPeersQuery
from lookup_manager import LookupManager
from node import Node

logger = logging.getLogger('dht')

class Controller:
    
    def __init__(self, dht_addr):
        my_addr = dht_addr
        my_id = identifier.RandomId()
        my_node = Node(my_addr, my_id)
        tracker_ = tracker.Tracker()
        token_m = token_manager.TokenManager()

        self.reactor = ThreadedReactor()
        rpc_m = RPCManager(self.reactor, my_addr[1])
        querier_ = Querier(rpc_m, my_id)
        routing_m = RoutingManager(my_node, querier_,
                                   bootstrap_nodes)
        responder_ = Responder(my_id, routing_m,
                              tracker_, token_m)

        responder_.set_on_query_received_callback(
            routing_m.on_query_received)
        querier_.set_on_response_received_callback(
            routing_m.on_response_received)
        querier_.set_on_error_received_callback(
            routing_m.on_error_received)
        querier_.set_on_timeout_callback(routing_m.on_timeout)
        querier_.set_on_nodes_found_callback(routing_m.on_nodes_found)

        routing_m.do_bootstrap()

        rpc_m.add_msg_callback(QUERY,
                               responder_.on_query_received)

        self.lookup_m = LookupManager(my_id, querier_,
                                      routing_m)
        self._routing_m = routing_m
        

    def start(self):
        self.reactor.start()

    def stop(self):
        #TODO2: stop each manager
        self.reactor.stop()

    def get_peers(self, info_hash, callback_f, bt_port=None):
        logger.critical('new lookup %r' % (info_hash))
        return self.lookup_m.get_peers(info_hash, callback_f, bt_port)

    def print_routing_table_stats(self):
        self._routing_m.print_stats()
    
bootstrap_nodes = (
    
    Node(('67.215.242.138', 6881)), #router.bittorrent.com
    Node(('192.16.127.98', 7005)), #KTH node
    )
