# Copyright (C) 2009 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

import message
import node
import sys

import logging

logger = logging.getLogger('dht')


class Responder(object ):
    "docstring for Responder"
    def __init__(self, my_id, routing_m, tracker, token_m):
        self.my_id = my_id
        self.routing_m = routing_m
        self.tracker = tracker
        self.token_m = token_m
        self.query_handler = {message.PING: self._on_ping,
                              message.FIND_NODE: self._on_find_node,
                              message.GET_PEERS: self._on_get_peers,
                              message.ANNOUNCE_PEER: self._on_announce_peer,
                              }
        self.notify_routing_m_on_query = None

    def set_on_query_received_callback(self, callback_f):
        self.notify_routing_m_on_query = callback_f
        
    def on_query_received(self, query_msg, addr):
        logger.debug('query received\n%s\nSource: %s' % (`query_msg`,
                                                          `addr`))
        try:
            handler = self.query_handler[query_msg.query]
        except (KeyError, ValueError):
            logger.exception('Invalid QUERY')
            return # ignore query #TODO2: send error back?
        response_msg = handler(query_msg)
        self.notify_routing_m_on_query(node.Node(addr,
                                                 query_msg.sender_id,
                                                 query_msg.ns_node))
        return response_msg

    def _on_ping(self, query_msg):
        return message.OutgoingPingResponse(self.my_id)

    def _on_find_node(self, query_msg):
        rnodes = self.routing_m.get_closest_rnodes(query_msg.target)
        return message.OutgoingFindNodeResponse(self.my_id,
                                                nodes2=rnodes)

    def _on_get_peers(self, query_msg):
        #get peers from the tracker (if any)
        token = self.token_m.get()
        peers = self.tracker.get(query_msg.info_hash)
        if peers:
            return message.OutgoingGetPeersResponse(self.my_id,
                                                    token,
                                                    peers=peers)
        rnodes = self.routing_m.get_closest_rnodes(query_msg.info_hash)
        return message.OutgoingGetPeersResponse(self.my_id,
                                                token,
                                                nodes2=rnodes)
    def _on_announce_peer(self, query_msg):
        return message.OutgoingAnnouncePeerResponse(self.my_id)
        
