# Copyright (C) 2009-2010 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

from nose.tools import ok_, eq_

import sys
import logging

import ptime as time
import node
import identifier
import message
from message import Datagram
import minitwisted
import test_const as tc

import querier
from querier import Querier
import logging_conf

logging_conf.testing_setup(__name__)
logger = logging.getLogger('dht')

import random
if random.random() > .8:
    RUN_CPU_INTENSIVE_TESTS = True
    print >>sys.stderr, '>>>>>>>>> Running cpu intensive tests in test_querier'
else:
    RUN_CPU_INTENSIVE_TESTS = False
    
TIMEOUT_DELAY = 3
LOOKUP_OBJ = 1

PYMDHT_VERSION = (11, 2, 3)
VERSION_LABEL = ''.join(
    ['NS',
     chr((PYMDHT_VERSION[0] - 11) * 24 + PYMDHT_VERSION[1]),
     chr(PYMDHT_VERSION[2])
     ])
  
clients_msg_f = message.MsgFactory(VERSION_LABEL, tc.CLIENT_ID)
servers_msg_f = message.MsgFactory(VERSION_LABEL, tc.SERVER_ID)

class TestQuerier:

    def setup(self):
        time.mock_mode()
        self.querier = Querier()#tc.CLIENT_ID)

    def test_generate_tids(self):
        #TODO: move to message
        if RUN_CPU_INTENSIVE_TESTS:
            num_tids =  pow(2, 16) + 2 #CPU intensive
        else:
            num_tids = 1000
        for i in xrange(num_tids):
            eq_(self.querier._next_tid(),
                chr(i%256)+chr((i/256)%256))

    def test_ping_with_reponse(self):
        # Client creates a query
        ping_msg = clients_msg_f.outgoing_ping_query(tc.SERVER_NODE)
        q = ping_msg
        # Client registers query
        timeout_ts, bencoded_msgs = self.querier.register_queries([q])
        # Client sends bencoded_msg
        # Server gets bencoded_msg and creates response
        ping_r_msg_out = servers_msg_f.outgoing_ping_response(tc.CLIENT_NODE)
        bencoded_r = ping_r_msg_out.stamp(ping_msg.tid)
        time.sleep(1)
        eq_(self.querier.get_timeout_queries()[1], [])
        # The client receives the bencoded message (after 1 second)
        ping_r_in = clients_msg_f.incoming_msg(
            Datagram(bencoded_r, tc.SERVER_ADDR))
        related_query = self.querier.get_related_query(ping_r_in)
        assert related_query is ping_msg

    def test_ping_with_timeout(self):
        # Client creates a query
        ping_msg = clients_msg_f.outgoing_ping_query(tc.SERVER_NODE)
        q = ping_msg
        # Client registers query
        bencoded_msg = self.querier.register_queries([q])
        # Client sends bencoded_msg
        time.sleep(3)
        # The server never responds and the timeout is triggered
        timeout_queries = self.querier.get_timeout_queries()
        eq_(len(timeout_queries[1]), 1)
        assert timeout_queries[1][0] is ping_msg

    def test_unsolicited_response(self):
        # Server creates unsolicited response
        # It might well be that the server responds using another port,
        # and therefore, the addr is not matched
        # TODO: consider accepting responses from a different port
        ping_r_msg_out = servers_msg_f.outgoing_ping_response(tc.CLIENT_NODE)
        bencoded_r = ping_r_msg_out.stamp('zz')
        # The client receives the bencoded message
        ping_r_in = clients_msg_f.incoming_msg(
                Datagram(bencoded_r, tc.SERVER_ADDR))
        related_query = self.querier.get_related_query(ping_r_in)
        assert related_query is None

    def test_response_with_different_tid(self):
        # Client creates a query
        ping_msg = clients_msg_f.outgoing_ping_query(tc.SERVER_NODE)
        q = ping_msg
        # Client registers query
        bencoded_msg = self.querier.register_queries([q])
        # Client sends bencoded_msg
        time.sleep(1)
        # Server gets bencoded_msg and creates response
        ping_r_msg_out = servers_msg_f.outgoing_ping_response(tc.CLIENT_NODE)
        bencoded_r = ping_r_msg_out.stamp('zz')
        # The client receives the bencoded message
        ping_r_in = clients_msg_f.incoming_msg(
                    Datagram(bencoded_r, tc.SERVER_ADDR))
        related_query = self.querier.get_related_query(ping_r_in)
        assert related_query is None
        
    def test_error_received(self):
        # Client creates a query
        msg = clients_msg_f.outgoing_ping_query(tc.SERVER_NODE)
        q = msg
        # Client registers query
        bencoded_msg = self.querier.register_queries([q])
        # Client sends bencoded_msg
        time.sleep(1)
        # Server gets bencoded_msg and creates response
        ping_r_msg_out = servers_msg_f.outgoing_error(tc.CLIENT_NODE,
                                                  message.GENERIC_E)
        bencoded_r = ping_r_msg_out.stamp(msg.tid)
        # The client receives the bencoded message
        ping_r_in = clients_msg_f.incoming_msg(
                    Datagram(bencoded_r, tc.SERVER_ADDR))
        related_query = self.querier.get_related_query(ping_r_in)
        assert related_query is msg

    def test_many_queries(self):
        # Client creates a query
        msgs = [clients_msg_f.outgoing_ping_query(
                tc.SERVER_NODE) for i in xrange(10)]
        queries = msgs
        # Client registers query
        bencoded_msg = self.querier.register_queries(queries)
        # Client sends bencoded_msg
        time.sleep(1)
        # response for queries[3]
        ping_r_msg_out = servers_msg_f.outgoing_ping_response(tc.CLIENT_NODE)
        bencoded_r = ping_r_msg_out.stamp(msgs[3].tid)
        ping_r_in = clients_msg_f.incoming_msg(
                        Datagram(bencoded_r, tc.SERVER_ADDR))
        related_query = self.querier.get_related_query(ping_r_in)
        assert related_query is msgs[3]
        # error for queries[2]
        ping_r_msg_out = servers_msg_f.outgoing_error(tc.CLIENT_NODE,
                                                  message.GENERIC_E)
        bencoded_r = ping_r_msg_out.stamp(msgs[2].tid)
        ping_r_in = clients_msg_f.incoming_msg(
                        Datagram(bencoded_r, tc.SERVER_ADDR))
        related_query = self.querier.get_related_query(ping_r_in)
        assert related_query is msgs[2]
        # response to wrong addr
        ping_r_msg_out = servers_msg_f.outgoing_ping_response(tc.CLIENT_NODE)
        bencoded_r = ping_r_msg_out.stamp(msgs[5].tid)
        ping_r_in = clients_msg_f.incoming_msg(
                        Datagram(bencoded_r, tc.SERVER2_ADDR))
        related_query = self.querier.get_related_query(ping_r_in)
        assert related_query is None
        # response with wrong tid
        ping_r_msg_out = servers_msg_f.outgoing_ping_response(tc.CLIENT_NODE)
        bencoded_r = ping_r_msg_out.stamp('ZZ')
        ping_r_in = clients_msg_f.incoming_msg(
                        Datagram(bencoded_r, tc.SERVER_ADDR))
        related_query = self.querier.get_related_query(ping_r_in)
        assert related_query is None
        # Still no time to trigger timeouts
        eq_(self.querier.get_timeout_queries()[1], [])
        time.sleep(1)
        # Now, the timeouts can be triggered
        timeout_queries = self.querier.get_timeout_queries()
        expected_msgs = msgs[:2] + msgs[4:]
        eq_(len(timeout_queries[1]), len(expected_msgs))
        for related_query, expected_msg in zip(
            timeout_queries[1], expected_msgs):
            assert related_query is expected_msg

    def teardown(self):
        time.normal_mode()

