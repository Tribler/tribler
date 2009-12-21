# Copyright (C) 2009 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

import time

from utils import log

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

class Controller:
    
    def __init__(self, dht_addr):
        self.my_addr = dht_addr
        self.my_id = identifier.RandomId()
        self.my_node = Node(self.my_addr, self.my_id)
        self.tracker = tracker.Tracker()
        self.token_m = token_manager.TokenManager()

        self.reactor = ThreadedReactor()
        self.rpc_m = RPCManager(self.reactor, self.my_addr[1])
        self.querier = Querier(self.rpc_m, self.my_id)
        self.routing_m = RoutingManager(self.my_node, self.querier,
                                        bootstrap_nodes)
        self.responder = Responder(self.my_id, self.routing_m,
                                   self.tracker, self.token_m)

        self.responder.set_on_query_received_callback(
            self.routing_m.on_query_received)
        self.querier.set_on_response_received_callback(
            self.routing_m.on_response_received)
        self.querier.set_on_error_received_callback(
            self.routing_m.on_error_received)
        self.querier.set_on_timeout_callback(self.routing_m.on_timeout)
        self.querier.set_on_nodes_found_callback(self.routing_m.on_nodes_found)

        self.routing_m.do_bootstrap()

        self.rpc_m.add_msg_callback(QUERY,
                                    self.responder.on_query_received)

        self.lookup_m = LookupManager(self.my_id, self.querier,
                                      self.routing_m)

    def start(self):
        self.reactor.start()

    def stop(self):
        #TODO2: stop each manager
        self.reactor.stop()

    def get_peers(self, info_hash, callback_f, bt_port=None):
        return self.lookup_m.get_peers(info_hash, callback_f, bt_port)

    
bootstrap_nodes = (
    
    Node(('67.215.242.138', 6881)), #router.bittorrent.com
    Node(('192.16.127.98', 7005)), #KTH node
    )
