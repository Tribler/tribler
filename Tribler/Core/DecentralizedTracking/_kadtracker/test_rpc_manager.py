# Copyright (C) 2009 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

from nose.tools import ok_, eq_, assert_raises

import logging, logging_conf

import minitwisted
import message
import test_const as tc

import rpc_manager


logging_conf.testing_setup(__name__)
logger = logging.getLogger('dht')
#FIXME: more tests!!!!

class TestRPCManager:

    def on_query_received(self, msg, addr):
        self.got_query = True
        return message.OutgoingPingResponse(tc.SERVER_ID)

    def on_response_received(self, msg, addr):
        self.got_response = True

    def on_routing_response_received(self, msg, addr):
        self.got_routing_response = True

    def on_error_received(self, msg, addr):
        self.got_error = True

    def on_timeout(self, addr):
        self.got_timeout = True

    def on_routing_timeout(self, addr):
        self.got_routing_timeout = True

    def setup(self):
        self.reactor = minitwisted.ThreadedReactor()
        self.c = rpc_manager.RPCManager(self.reactor,
                                        tc.CLIENT_ADDR[1])
        self.s = rpc_manager.RPCManager(self.reactor,
                                        tc.SERVER_ADDR[1])

        self.got_query = False
        self.got_response = False
        self.got_routing_response = False
        self.got_error = False
        self.got_timeout = False
        self.got_routing_timeout = False
        
    def test_querier_responder(self):
        # client
        # setup
        self.c.add_msg_callback(message.RESPONSE,
                                self.on_response_received)
        self.c.add_msg_callback(message.RESPONSE,
                                self.on_routing_response_received)
        self.c.add_msg_callback(message.ERROR,
                                self.on_error_received)
        self.c.add_timeout_callback(self.on_routing_timeout)

        # server
        # setup
        self.s.add_msg_callback(message.QUERY,
                                self.on_query_received)
        
        # client creates and sends query
        t_task = self.c.get_timeout_task(tc.SERVER_ADDR,
                                         tc.TIMEOUT_DELAY,
                                         self.on_timeout)
        msg = message.OutgoingPingQuery(tc.CLIENT_ID)
        msg_data = msg.encode(tc.TID)
        self.c.send_msg_to(msg_data, tc.SERVER_ADDR)
        # client sets up timeout

        # server receives query, creates response and sends it back
        self.s._on_datagram_received(msg_data, tc.CLIENT_ADDR)
        # rpc_manager would send the message back automatically
        ok_(self.got_query); self.got_query = False
        msg = message.OutgoingPingResponse(tc.SERVER_ID)
        msg_data = msg.encode(tc.TID)
        self.s.send_msg_to(msg_data, tc.CLIENT_ADDR)

        # client gets response
        self.c._on_datagram_received(msg_data, tc.SERVER_ADDR)
        ok_(self.got_response); self.got_response = False
        ok_(self.got_routing_response)
        self.got_routing_response = False
        
        # client gets error
        msg_data = message.OutgoingErrorMsg(message.GENERIC_E
                                            ).encode(tc.TID)
        self.c._on_datagram_received(msg_data, tc.SERVER_ADDR)
        ok_(self.got_error); self.got_error = False

        # client gets timeout
        t_task.fire_callbacks()
        ok_(self.got_timeout); self.got_timeout = False
        ok_(self.got_routing_timeout)
        self.got_routing_timeout = False
        
        # server gets invalid message
        self.s._on_datagram_received('zzz', tc.CLIENT_ADDR)
        ok_(not self.got_query)
        ok_(not self.got_response)
        ok_(not self.got_routing_response)


    def test_call_later(self):
        t = self.c.call_later(tc.TIMEOUT_DELAY,
                              self.on_timeout,
                              1234)
        t.fire_callbacks()
        ok_(self.got_timeout)

    def test_no_callback_for_type(self):
        msg = message.OutgoingPingQuery(tc.CLIENT_ID)
        msg_data = msg.encode(tc.TID)
        self.s._on_datagram_received(msg_data,
                                     tc.CLIENT_ADDR)
        ok_(not self.got_query)
        ok_(not self.got_response)
        ok_(not self.got_routing_response)
        
    def teardown(self):
        self.c.stop()
        self.s.stop()
