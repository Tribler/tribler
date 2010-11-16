# Copyright (C) 2009 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

from nose.tools import *

import  message

import logging, logging_conf
import test_const as tc

import routing_manager
import token_manager
import tracker
import responder

logging_conf.testing_setup(__name__)
logger = logging.getLogger('dht')


class TestResponder:

    def _notify_routing_m(self, node):
        self.notification_callback_done = True

    def setup(self):
        routing_m = routing_manager.RoutingManagerMock()
        self.tracker = tracker.Tracker()
        self.token_m = token_manager.TokenManager()
        self.responder = responder.Responder(tc.SERVER_ID, routing_m,
                                             self.tracker, self.token_m)
        self.notification_callback_done = False
        self.responder.set_on_query_received_callback(self._notify_routing_m)

    def test_return_response_for_ping(self):
        # client side
        query_msg = message.OutgoingPingQuery(tc.CLIENT_ID)
        # rpc_manager.sendto() encodes
        query_data = query_msg.encode(tc.TID)
        # server side
        # rpc_manager.datagram_received() decodes
        query_msg = message.IncomingMsg(query_data)
        assert not self.notification_callback_done
        response_msg = self.responder.on_query_received(query_msg,
                                                         tc.CLIENT_ADDR)
        response_data = response_msg.encode(query_msg.tid)

        assert self.notification_callback_done
        expected_msg = message.OutgoingPingResponse(tc.SERVER_ID)
        expected_data = expected_msg.encode(tc.TID)
        eq_(response_data, expected_data)
    
    def test_return_response_for_find_node(self):
        # client side
        query_msg = message.OutgoingFindNodeQuery(tc.CLIENT_ID,
                                                  tc.TARGET_ID)
        # querier encodes
        query_data = query_msg.encode(tc.TID)
        # server side
        # rpc_manager.datagram_received() decodes
        query_msg = message.IncomingMsg(query_data)
        # rpc calls responder
        assert not self.notification_callback_done
        response_msg = self.responder.on_query_received(query_msg,
                                                        tc.CLIENT_ADDR)
        response_data = response_msg.encode(query_msg.tid)
        assert self.notification_callback_done
        expected_msg = message.OutgoingFindNodeResponse(tc.SERVER_ID,
                                                        tc.NODES)
        expected_data = expected_msg.encode(tc.TID)
        eq_(response_data, expected_data)
    
    def test_return_response_for_get_peers_when_peers(self):
        # server's tracker has peers
        for peer in tc.PEERS:
            self.tracker.put(tc.INFO_HASH, peer)

        # client side
        query_msg = message.OutgoingGetPeersQuery(tc.CLIENT_ID,
                                                  tc.INFO_HASH) 
        # querier encodes
        query_data = query_msg.encode(tc.TID)
        # server side
        # rpc_manager.datagram_received() decodes
        query_msg = message.IncomingMsg(query_data)
        # rpc calls responder
        assert not self.notification_callback_done
        response_msg = self.responder.on_query_received(query_msg,
                                                        tc.CLIENT_ADDR)
        response_data = response_msg.encode(query_msg.tid)
        assert self.notification_callback_done
        expected_msg = message.OutgoingGetPeersResponse(tc.SERVER_ID,
                                                        self.token_m.get(),
                                                        peers=tc.PEERS)
        expected_data = expected_msg.encode(tc.TID)
        eq_(response_data, expected_data)
    
    def test_return_response_for_get_peers_when_no_peers(self):
        # client side
        query_msg = message.OutgoingGetPeersQuery(tc.CLIENT_ID, tc.NODE_ID)
        # rpc_manager.sendto() encodes
        query_data = query_msg.encode(tc.TID) 
        # server side
        # rpc_manager.datagram_received() decodes
        query_msg = message.IncomingMsg(query_data)
        assert not self.notification_callback_done
        response_msg = self.responder.on_query_received(query_msg,
                                                        tc.CLIENT_ADDR)
        response_data = response_msg.encode(query_msg.tid)
        assert self.notification_callback_done
        expected_msg = message.OutgoingGetPeersResponse(tc.SERVER_ID,
                                                        self.token_m.get(),
                                                        nodes2=tc.NODES)
        expected_data = expected_msg.encode(query_msg.tid)
        eq_(response_data, expected_data)
    
    def test_return_response_for_announce_peer_with_valid_tocken(self):
        # client side
        query_msg = message.OutgoingAnnouncePeerQuery(tc.CLIENT_ID,
                                                      tc.INFO_HASH,
                                                      tc.CLIENT_ADDR[1],
                                                      self.token_m.get())
        # querier.send_query() encodes
        query_data = query_msg.encode(tc.TID)
        # server side
        # rpc_manager.datagram_received() decodes and calls responder (callback)
        query_msg = message.IncomingMsg(query_data)
        assert not self.notification_callback_done
        response_msg = self.responder.on_query_received(query_msg,
                                                         tc.CLIENT_ADDR)
        response_data = response_msg.encode(query_msg.tid)
        assert self.notification_callback_done
        # responder returns to querier
        expected_msg = message.OutgoingAnnouncePeerResponse(tc.SERVER_ID)
        expected_data = expected_msg.encode(tc.TID)
        assert response_data == expected_data

    def test_errors(self):
        # client side
        query_msg = message.OutgoingPingQuery(tc.CLIENT_ID)
        # querier.send_query() encodes
        query_data = query_msg.encode(tc.TID)
        # server side
        # rpc_manager.datagram_received() decodes and calls responder (callback)
        query_msg = message.IncomingMsg(query_data)
        ## 'xxxxxx' is not a valid QUERY
        query_msg.query = 'zzzzzzzz'
        assert not self.notification_callback_done
        ok_(self.responder.on_query_received(query_msg,
                                             tc.CLIENT_ADDR) is None)


    
