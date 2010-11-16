# Copyright (C) 2009-2010 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

from nose.tools import ok_, eq_

import sys
import logging, logging_conf

import node
import identifier
import message
import minitwisted
import test_const as tc
from testing_mocks import MockTime

import querier
from querier import Query, Querier

logging_conf.testing_setup(__name__)
logger = logging.getLogger('dht')


RUN_CPU_INTENSIVE_TESTS = False
RUN_NETWORK_TESTS = False # Requires a running external DHT node

TIMEOUT_DELAY = 3
LOOKUP_OBJ = 1

class TestQuery:

    def setup(self):
        global time
        time = querier.time = MockTime()
        
    def test_ping_with_response(self):
        # Client creates a query
        ping_msg = message.OutgoingPingQuery(tc.CLIENT_ID)
        q = Query(ping_msg, tc.SERVER_NODE)
        # Querier.register_query sets a TID and timeout_task
        q.tid = tc.TID
        q.timeout_task = minitwisted.Task(TIMEOUT_DELAY, None)
        q.query_ts = time.time()
        # The query is sent
        time.sleep(1)
        # The server creates a response
        ping_r_msg_out = message.OutgoingPingResponse(tc.SERVER_ID)
        bencoded_r = ping_r_msg_out.encode(tc.TID)
        # The client receives the bencoded message
        ping_r_in = message.IncomingMsg(bencoded_r,
                                        tc.SERVER_ADDR)
        q.on_response_received(ping_r_in)
        assert 1 < q.rtt < 1.1
        assert q.lookup_obj is None
    
    def test_get_peers_with_response(self):
        # Client creates a query
        fn_msg = message.OutgoingGetPeersQuery(tc.CLIENT_ID,
                                               tc.INFO_HASH)
        # the destination's ID is unknown
        # This query belongs to a lookup
        q = Query(fn_msg, node.Node(tc.SERVER_ADDR), LOOKUP_OBJ)
        # Querier.register_query sets a TID and timeout_task
        q.tid = tc.TID
        q.timeout_task = minitwisted.Task(TIMEOUT_DELAY, None)
        q.query_ts = time.time()
        # The query is sent
        # The server creates a response
        fn_r_out = message.OutgoingGetPeersResponse(tc.SERVER_ID,
                                                    nodes=tc.NODES)
        bencoded_fn_r = fn_r_out.encode(tc.TID)
        time.sleep(1)
        # The client receives the bencoded message
        fn_r_in = message.IncomingMsg(bencoded_fn_r,
                                      tc.SERVER_ADDR)
        q.on_response_received(fn_r_in)
        assert 1 < q.rtt < 1.1
        assert q.lookup_obj is LOOKUP_OBJ

    def test_find_node_with_error(self):
        # Client creates a query
        fn_msg = message.OutgoingFindNodeQuery(tc.CLIENT_ID,
                                               tc.TARGET_ID)
        # the destination's ID is unknown
        q = Query(fn_msg, node.Node(tc.SERVER_ADDR))
        # Querier.register_query sets a TID and timeout_task
        q.tid = tc.TID
        q.timeout_task = minitwisted.Task(TIMEOUT_DELAY, None)
        q.query_ts = time.time()
        # The query is sent
        # The server creates a response
        fn_r_out = message.OutgoingErrorMsg(message.GENERIC_E)
        bencoded_fn_r = fn_r_out.encode(tc.TID)
        time.sleep(1)
        # The client receives the bencoded message
        fn_r_in = message.IncomingMsg(bencoded_fn_r,
                                      tc.SERVER_ADDR)
        q.on_error_received(fn_r_in)
        assert 1 < q.rtt < 1.1
        assert q.lookup_obj is None


class TestQuerier:

    def setup(self):
        global time
        time = querier.time = MockTime()
        self.querier = Querier(tc.CLIENT_ID)

    def test_generate_tids(self):
        #TODO: move to message
        num_tids = 1000
        if RUN_CPU_INTENSIVE_TESTS:
            num_tids =  pow(2, 16) + 2 #CPU intensive
        for i in xrange(num_tids):
            eq_(self.querier._next_tid(),
                chr(i%256)+chr((i/256)%256))

    def test_ping_with_reponse(self):
        # Client creates a query
        ping_msg = message.OutgoingPingQuery(tc.CLIENT_ID)
        q = Query(ping_msg, tc.SERVER_NODE)
        timeout_task = minitwisted.Task(TIMEOUT_DELAY, None)
        # Client registers query
        bencoded_msg = self.querier.register_query(q, timeout_task)
        # Client sends bencoded_msg
        time.sleep(1)
        # Server gets bencoded_msg and creates response
        ping_r_msg_out = message.OutgoingPingResponse(tc.SERVER_ID)
        bencoded_r = ping_r_msg_out.encode(q.tid)
        # The client receives the bencoded message
        ping_r_in = message.IncomingMsg(bencoded_r,
                                        tc.SERVER_ADDR)
        stored_q = self.querier.on_response_received(ping_r_in,
                                                     tc.SERVER_ADDR)
        assert stored_q is q

    def test_ping_with_timeout(self):
        # Client creates a query
        ping_msg = message.OutgoingPingQuery(tc.CLIENT_ID)
        q = Query(ping_msg, tc.SERVER_NODE)
        timeout_task = minitwisted.Task(TIMEOUT_DELAY, None)
        # Client registers query
        bencoded_msg = self.querier.register_query(q, timeout_task)
        # Client sends bencoded_msg
        time.sleep(3)
        # The server never responds and the timeout is triggered
        stored_q = self.querier.on_timeout(tc.SERVER_ADDR)
        assert stored_q is q

    def test_unsolicited_response(self):
        # Server creates unsolicited response
        # It might well be that the server responds using another port,
        # and therefore, the addr is not matched
        # TODO: consider accepting responses from a different port
        ping_r_msg_out = message.OutgoingPingResponse(tc.SERVER_ID)
        bencoded_r = ping_r_msg_out.encode('zz')
        # The client receives the bencoded message
        ping_r_in = message.IncomingMsg(bencoded_r,
                                        tc.SERVER_ADDR)
        stored_q = self.querier.on_response_received(ping_r_in,
                                                     tc.SERVER_ADDR)
        assert stored_q is None

    def test_response_with_different_tid(self):
        # Client creates a query
        ping_msg = message.OutgoingPingQuery(tc.CLIENT_ID)
        q = Query(ping_msg, tc.SERVER_NODE)
        timeout_task = minitwisted.Task(TIMEOUT_DELAY, None)
        # Client registers query
        bencoded_msg = self.querier.register_query(q, timeout_task)
        # Client sends bencoded_msg
        time.sleep(1)
        # Server gets bencoded_msg and creates response
        ping_r_msg_out = message.OutgoingPingResponse(tc.SERVER_ID)
        bencoded_r = ping_r_msg_out.encode('zz')
        # The client receives the bencoded message
        ping_r_in = message.IncomingMsg(bencoded_r,
                                        tc.SERVER_ADDR)
        stored_q = self.querier.on_response_received(ping_r_in,
                                                     tc.SERVER_ADDR)
        assert stored_q is None

    def test_error(self):
        # Client creates a query
        ping_msg = message.OutgoingPingQuery(tc.CLIENT_ID)
        q = Query(ping_msg, tc.SERVER_NODE)
        timeout_task = minitwisted.Task(TIMEOUT_DELAY, None)
        # Client registers query
        bencoded_msg = self.querier.register_query(q, timeout_task)
        # Client sends bencoded_msg
        time.sleep(1)
        # Server gets bencoded_msg and creates response
        ping_r_msg_out = message.OutgoingErrorMsg(message.GENERIC_E)
        bencoded_r = ping_r_msg_out.encode(tc.TID)
        # The client receives the bencoded message
        ping_r_in = message.IncomingMsg(bencoded_r,
                                        tc.SERVER_ADDR)
        stored_q = self.querier.on_error_received(ping_r_in,
                                                  tc.SERVER_ADDR)
        assert stored_q is None


        

    def tear_down(self):
        global time
        time.unmock()
        time = querier.time = time.actual_time

        
class OldTestQuery:
        
    def _setup(self):
        global time
        time = querier.time = MockTime()
        
        self.ping_msg = message.OutgoingPingQuery(tc.CLIENT_ID)
        ping_r_out = message.OutgoingPingResponse(tc.SERVER_ID)
        self.ping_r_in = message.IncomingMsg(ping_r_out.encode(tc.TID),
                                             tc.SERVER_ADDR)
        fn_r_out = message.OutgoingFindNodeResponse(tc.SERVER_ID,
                                                    nodes2=tc.NODES)
        self.fn_r_in = message.IncomingMsg(fn_r_out.encode(tc.TID),
                                           tc.SERVER_ADDR)

        self.got_response = False
        self.got_error = False
        self.got_timeout = False
        
        self.got_routing_response = False
        self.got_routing_error = False
        self.got_routing_timeout = False
        self.got_routing_nodes_found = False

        timeout_task = minitwisted.Task(1, self.on_timeout,
                                        tc.SERVER_NODE)
        self.query = querier.Query(tc.TID, self.ping_msg.query, tc.SERVER_NODE,
                                   timeout_task)
        
    def on_response(self, response_msg, addr):
        self.got_response = True

    def on_error(self, error_msg, addr):
        self.got_error = True

    def on_timeout(self, addr):
        self.got_timeout = True

    def on_routing_response(self, node_, rtt):
        self.got_routing_response = True

    def on_routing_error(self, node_):
        self.got_routing_error = True

    def on_routing_timeout(self, node_):
        self.got_routing_timeout = True

    def on_routing_nodes_found(self, node_):
        self.got_routing_nodes_found = True


    def _test_fire_callback_on_response(self):
        # the server creates the response
        pong_msg = message.OutgoingPingResponse(tc.SERVER_ID)
        pong_data = pong_msg.encode(tc.TID)
        # IncomingMsg decodes the response received
        pong_msg = message.IncomingMsg(pong_data, tc.SERVER_ADDR)
        # querier notifies of the message (callback)
        self.query.on_response_received(pong_msg)
        ok_(self.got_response)
        ok_(not self.got_error)
        ok_(not self.got_timeout)

    def _test_fire_callback_on_error(self):
        # the server creates the response
        error_msg = message.OutgoingErrorMsg(message.GENERIC_E)
        error_data = error_msg.encode(tc.TID)
        # IncomingMsg decodes the response received
        error_msg = message.IncomingMsg(error_data, tc.SERVER_ADDR)
        # querier notifies of the message (callback)
        self.query.on_error_received(error_msg)
        assert not self.got_response and self.got_error
    '''
    def _test_on_timeout(self):
        ok_(not self.got_timeout)
        ok_(not self.got_routing_timeout)
        self.query.on_timeout()
        ok_(self.got_timeout)
        ok_(self.got_routing_timeout)
    '''        
    def test_fire_callback_on_timeout(self):
        self.query.timeout_task.fire_callbacks()
        self.query.timeout_task.cancel()
        assert not self.got_response and not self.got_error \
               and self.got_timeout
        
    def test_fire_callback_on_late_response(self):
        self.query.timeout_task.fire_callbacks()
        self.query.timeout_task.cancel()
        # the server creates the response
        pong_msg = message.OutgoingPingResponse(tc.SERVER_ID)
        pong_data = pong_msg.encode(tc.TID)
        # IncomingMsg decodes the response received
        pong_msg = message.IncomingMsg(pong_data, tc.SERVER_ADDR)
        # querier notifies of the message (but it's too late)
        self.query.on_response_received(pong_msg)
        logger.warning(
            "**IGNORE WARNING LOG**")
        assert not self.got_response and not self.got_error \
               and self.got_timeout
        
    def test_invalid_response_received(self):
        # Response received is invalid
        self.ping_r_in._msg_dict[message.RESPONSE] = 'zz'
        ok_(not self.got_response) 
        logger.warning(
            "**IGNORE WARNING LOG**")
        self.query.on_response_received(self.ping_r_in)
        ok_(not self.got_response)

    def _test_response_contains_nodes(self):
        # Trick query to accept find node response
        self.query.query = message.FIND_NODE
        ok_(not self.got_response)
        ok_(not self.got_routing_response)
        ok_(not self.got_routing_nodes_found)
        self.query.on_response_received(self.fn_r_in)
        ok_(self.got_response)
        ok_(self.got_routing_response)
        ok_(self.got_routing_nodes_found)

    def _test_different_node_id(self):
        # We are expecting response from SERVER_NODE
        # Here we test if the response contains an ID
        # different to SERVER_ID
        self.query.node = node.Node(tc.SERVER_ADDR,
                                    tc.CLIENT_ID)
        ok_(not self.got_response)
        ok_(not self.got_routing_response)
        ok_(not self.got_routing_nodes_found)
        self.query.on_response_received(self.fn_r_in)
        ok_(not self.got_response)
        ok_(not self.got_routing_response)
        ok_(not self.got_routing_nodes_found)

    def teardown(self):
        global time
        time.unmock()
        time = querier.time = time.actual_time

'''
class _OldTestQuerier:
    
    def setup(self):
        import rpc_manager
        global time

        time = minitwisted.time = querier.time = MockTime()

        self.got_response = False
        self.got_timeout = False
        self.got_error = False

        self.querier = querier.Querier(tc.CLIENT_ID)

        self.r = minitwisted.ThreadedReactor(task_interval=.01)
        self.rpc_m = rpc_manager.RPCManager(self.r)
        self.querier = querier.Querier(tc.CLIENT_NODE)
        self.r.start()
        
    def on_response(self, response_msg, node_):
        self.got_response = True

    def on_timeout(self, node_):
        self.got_timeout = True

    def on_error(self, error_msg, node_):
        self.got_error = True

    def on_routing_response(self, node_):
        self.got_routing_response = True

    def on_routing_error(self, node_):
        self.got_routing_error = True

    def on_routing_timeout(self, node_):
        self.got_routing_timeout = True

    def on_routing_nodes_found(self, node_):
        self.got_routing_nodes_found = True



    def send_query_and_get_response(self, querier_, later_delay=0):
        ping_msg = message.OutgoingPingQuery(tc.CLIENT_ID)
        msg = message.OutgoingFindNodeQuery(tc.CLIENT_ID,
                                                 tc.CLIENT_ID)
        if later_delay:
            task = querier_.send_query_later(later_delay,
                                             msg,
                                             tc.EXTERNAL_NODE,
                                             self.on_response,
                                             self.on_timeout,
                                             self.on_error,
                                             tc.TIMEOUT_DELAY)
            # This second query is just to have two elements
            # in the querier_.pending[tc.EXTERNAL_ADDR] list
            task = querier_.send_query_later(later_delay,
                                             msg,
                                             tc.EXTERNAL_NODE,
                                             self.on_response,
                                             self.on_timeout,
                                             self.on_error,
                                             tc.TIMEOUT_DELAY)
        else:
            node_ = (querier_ == self.querier) and tc.SERVER_NODE
            query = querier_.send_query(ping_msg, node_ or tc.EXTERNAL_NODE,
                                        self.on_response,
                                        self.on_timeout, self.on_error,
                                        timeout_delay=tc.TIMEOUT_DELAY)
        # querier creates TID
        msg_tid = '\0\0'
        if querier_ is self.querier_mock:
            # server gets query
            # the server creates the response
            pong_msg = message.OutgoingPingResponse(tc.SERVER_ID)
            pong_msg_data = pong_msg.encode(msg_tid)
            # the client gets the response
            # rpc_m decodes msg and calls callback
            pong_msg = message.IncomingMsg(pong_msg_data, tc.SERVER_ADDR)
            querier_.on_response_received(pong_msg, tc.SERVER_ADDR)
        if later_delay:
            ok_(not self.got_response)
            ok_(not self.got_timeout)
            time.sleep(later_delay*2)
        time.sleep(tc.TIMEOUT_DELAY+.1)
        ### It crashed (timeout_task.cancelled??????)


        #TODO2: move the 'real' tests to integration
        
        ###############################################
        ### A DHT node must be running on peer_addr ###
        ###############################################
        ok_(self.got_response)
        ok_(not self.got_timeout)
        ###############################################
        ###############################################

    def send_query_and_get_error(self, querier):


        ping_msg = message.OutgoingPingQuery()
        query = querier.send_query(ping_msg, tc.EXTERNAL_NODE,
                                   self.on_response,
                                   self.on_timeout, self.on_error,
                                   timeout_delay=tc.TIMEOUT_DELAY)
        if querier is self.querier_mock:
            # the server creates the response
            error_msg = message.OutgoingErrorMsg(query.tid,
                                                 message.GENERIC_E)
            error_data = error_msg.encode()
            # rpc_m decodes the response received
            _, _, error_msg_dict = message.IncomingMsg(error_data,
                                                       tc.SERVER_ADDR)
            # rpc_m notifies of the message (callback)
            querier.on_error_received(error_msg_dict, tc.EXTERNAL_NODE)
        time.sleep(tc.TIMEOUT_DELAY + .1)
        
        ### It crashed (timeout_task.cancelled??????)


        #TODO2: move the 'real' tests to integration
        
        ###############################################
        ### A DHT node must be running on peer_addr ###
        ###############################################
        ########## assert self.got_response and not self.got_timeout
        ###############################################
        ###############################################



    def send_query_and_get_timeout(self, querier):
        ping_msg = message.OutgoingPingQuery(tc.CLIENT_ID)
        query = querier.send_query(ping_msg, tc.DEAD_NODE,
                                   self.on_response,
                                   self.on_timeout, self.on_error,
                                   timeout_delay=tc.TIMEOUT_DELAY)
        if querier is self.querier_mock:
            query.timeout_task.fire_callbacks()
        time.sleep(tc.TIMEOUT_DELAY + .1)
        ok_(not self.got_response)
        ok_(self.got_timeout)

    def _test_send_query_mock(self):
        self.send_query_and_get_response(self.querier_mock)
        ok_(not self.got_routing_response)
        ok_(not self.got_routing_nodes_found)
        ok_(not self.got_routing_timeout)

    def _test_send_query(self):
        if RUN_NETWORK_TESTS:
            self.send_query_and_get_response(self.querier)
            ok_(not self.got_routing_response)
            ok_(not self.got_routing_nodes_found)
            ok_(not self.got_routing_timeout)

    def _test_send_query_routing(self):
        if RUN_NETWORK_TESTS:
            self.send_query_and_get_response(self.querier_routing)
            ok_(self.got_routing_response)
            ok_(not self.got_routing_nodes_found)
            ok_(not self.got_routing_timeout)

    def _test_send_query_timeout_mock(self):
        self.send_query_and_get_timeout(self.querier_mock)
        ok_(not self.got_routing_response)
        ok_(not self.got_routing_nodes_found)
        ok_(not self.got_routing_timeout)

    def _test_send_query_timeout(self):
        self.send_query_and_get_timeout(self.querier)
        ok_(not self.got_routing_response)
        ok_(not self.got_routing_nodes_found)
        ok_(not self.got_routing_timeout)

    def _test_send_query_timeout_routing(self):
        self.send_query_and_get_timeout(self.querier_routing)
        ok_(not self.got_routing_response)
        ok_(not self.got_routing_nodes_found)
        ok_(self.got_routing_timeout)

    def _test_send_query_later(self):
        if RUN_NETWORK_TESTS:
            self.send_query_and_get_response(self.querier_routing, .001)
            ok_(self.got_routing_response)
            ok_(self.got_routing_nodes_found)
            ok_(not self.got_routing_timeout)

    def _test_unsolicited_response(self):
        # We have a pending response from NO_ADDR (TID \0\0)
        # but we get a response with different TID

        # client
        ping = message.OutgoingPingQuery(tc.CLIENT_ID)
        self.querier.send_query(ping,
                                tc.SERVER_NODE,
                                self.on_response,
                                self.on_error,
                                self.on_timeout,
                                tc.TIMEOUT_DELAY)
        ok_(not self.got_response)
        ok_(not self.got_routing_response)
        ok_(not self.got_routing_nodes_found)
        # server
        pong = message.OutgoingPingResponse(tc.SERVER_ID)
        pong_in = message.IncomingMsg(pong.encode(tc.TID), tc.SERVER_ADDR)
        # client
        self.querier.on_response_received(pong_in,
                                               tc.SERVER_ADDR)
        ok_(not self.got_response)
        ok_(not self.got_routing_response)
        ok_(not self.got_routing_nodes_found)

    def test_error(self):
        msg = message.OutgoingErrorMsg(message.GENERIC_E)
        self.querier.on_error_received(msg, tc.SERVER_ADDR)


    def teardown(self):
        self.r.stop()
        global time
        time = minitwisted.time = querier.time = time.actual_time

'''
