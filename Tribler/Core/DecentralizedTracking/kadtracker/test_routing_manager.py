# Copyright (C) 2009 Raul Jimenez
# Released under GNU LGPL 2.1
# See LICENSE.txt for more information

from nose.tools import ok_, eq_, assert_raises

import test_const as tc

import minitwisted
import rpc_manager
import querier
import message

from routing_manager import RoutingManager, RoutingManagerMock

import logging, logging_conf

logging_conf.testing_setup(__name__)
logger = logging.getLogger('dht')


class TestRoutingManager:

    def setup(self):
        for n in tc.NODES + [tc.SERVER_NODE, tc.SERVER2_NODE]:
            n.is_ns = False
        for n in tc.NODES2 + [tc.CLIENT_NODE]:
            n.is_ns = True
        
        self.querier = querier.QuerierMock(tc.CLIENT_ID)
        self.routing_m = RoutingManager(tc.CLIENT_NODE, self.querier,
                                        tc.NODES)

    def exercise_mock(self, mode):
        # If this happens, we want to know
        assert_raises(Exception, self.routing_m.on_timeout, tc.CLIENT_NODE)

        # node is nowhere (timeout is ignored)
        self.routing_m.on_timeout(tc.SERVER_NODE)

        # main: CLIENT_NODE, replacement: empty
        eq_(self.routing_m.get_closest_rnodes(tc.SERVER_ID),
            [tc.CLIENT_NODE])

        self.routing_m.on_response_received(tc.SERVER_NODE)
        # main: client_node, server_node, replacement: empty

        # this should reset refresh task
        self.routing_m.on_response_received(tc.SERVER_NODE)

        eq_(self.routing_m.get_closest_rnodes(tc.SERVER_ID),
            [tc.SERVER_NODE, tc.CLIENT_NODE])

        self.routing_m.on_timeout(tc.SERVER_NODE)
        # main: client_node, replacement: server_node
        eq_(self.routing_m.get_closest_rnodes(tc.SERVER_ID),
            [tc.CLIENT_NODE])

        self.routing_m.on_response_received(tc.SERVER2_NODE)
        # main: client_node, server_node, replacement: server2_node(q)
        eq_(self.routing_m.get_closest_rnodes(tc.SERVER_ID),
            [tc.SERVER2_NODE, tc.CLIENT_NODE])

        self.routing_m.on_response_received(tc.SERVER_NODE)
        # main: client_node, server_node, replacement: server2_node(q)
        eq_(self.routing_m.get_closest_rnodes(tc.SERVER_ID),
            [tc.SERVER_NODE, tc.SERVER2_NODE, tc.CLIENT_NODE])
        eq_(self.routing_m.get_closest_rnodes(tc.SERVER2_ID),
            [tc.SERVER2_NODE, tc.CLIENT_NODE])
        eq_(self.routing_m.get_closest_rnodes(tc.CLIENT_ID),
            [tc.CLIENT_NODE])
        for n in tc.NODES:
            self.routing_m.on_response_received(n)
        """
        Main Routing Table
        # -1
        client
        # 154
        server2
        # 159
        server nodes[0:7]
        """
        eq_(self.routing_m.get_closest_rnodes(tc.CLIENT_ID),
            [tc.CLIENT_NODE])
        for n in tc.NODES:
            eq_(self.routing_m.get_closest_rnodes(n.id),
                [tc.SERVER_NODE] + tc.NODES[:7])
        # bucket full (NODES[7] in replacement
            
        self.routing_m.on_query_received(tc.NODES[7])
        eq_(self.routing_m.get_closest_rnodes(n.id),
            [tc.SERVER_NODE] + tc.NODES[:7])
        
        # nodes[0] is kicked out from main
        # all nodes in replacement are refreshed (pinged)
        self.routing_m.on_timeout(tc.NODES[0])
        eq_(self.routing_m.get_closest_rnodes(tc.NODES[0].id),
            [tc.SERVER_NODE] + tc.NODES[1:7] + [tc.SERVER2_NODE])

        # nodes[7] is refreshed
        self.routing_m.on_query_received(tc.NODES[7])
        # nodes[7] still in replacement (queries don't cause movements)
        eq_(self.routing_m.get_closest_rnodes(tc.NODES[0].id),
            [tc.SERVER_NODE] + tc.NODES[1:7] + [tc.SERVER2_NODE])

        # nodes[7] is moved to the main table (response to refresh ping)
        self.routing_m.on_response_received(tc.NODES[7])
        eq_(self.routing_m.get_closest_rnodes(tc.NODES[0].id),
            [tc.SERVER_NODE] + tc.NODES[1:8])

        # nodes[7] is refreshed (no change to the tables)
        self.routing_m.on_query_received(tc.NODES[7])
        eq_(self.routing_m.get_closest_rnodes(tc.NODES[0].id),
            [tc.SERVER_NODE] + tc.NODES[1:8])

        # nodes[7] is in main and get response
        self.routing_m.on_response_received(tc.NODES[7])
        

        # nodes[0] gets strike 2, 3 and 4 (timeouts)
        self.routing_m.on_timeout(tc.NODES[0])
        self.routing_m.on_timeout(tc.NODES[0])
        self.routing_m.on_timeout(tc.NODES[0])
        # and can be expelled from the replacement table
        # nodes2[:] send responses

        #TODO2: rnode(nodes[0] report 5 timeouts
        eq_(self.routing_m.replacement.get_rnode(
                tc.NODES[0]).timeouts_in_a_row(), 5)
            
        if mode is message.QUERY:
            for n in tc.NODES2:
                self.routing_m.on_query_received(n)
        elif mode is message.RESPONSE:
            for n in tc.NODES2:
                self.routing_m.on_response_received(n)
        # nodes[0] comes back but the repl bucket is full
        self.routing_m.on_response_received(tc.NODES[0])
        # nodes[0] sends error (routing manager ignores it)
        self.routing_m.on_error_received(tc.NODES[0])

        # timeout from node without id (ignored)
                # nodes[0] comes back but the repl bucket is full
        self.routing_m.on_timeout(tc.EXTERNAL_NODE)

        # nodes found (but no room in main
        self.routing_m.on_nodes_found(tc.NODES)
        
        # nodes[1] (in main) timeout and repl bucket is full
        # find worst node in repl (nodes[7]) and replace it
        # all nodes in repl bucket get refreshed (not nodes[1]
        self.routing_m.on_timeout(tc.NODES[1])
        eq_(self.routing_m.get_closest_rnodes(tc.NODES[0].id),
            [tc.SERVER_NODE] + tc.NODES[2:8] +[tc.SERVER2_NODE])

        # nodes found (there is room now)
        # nodes2[0:1] get refreshed (pinged
        self.routing_m.on_nodes_found(tc.NODES2)
        # nodes2[0] replies (and is added to main)
        self.routing_m.on_response_received(tc.NODES2[0])
        eq_(self.routing_m.get_closest_rnodes(tc.NODES2[0].id),
            [tc.SERVER_NODE] + tc.NODES[2:8] +tc.NODES2[0:1])


        if mode == message.QUERY:
            expected_main = [tc.SERVER2_NODE] + \
                [tc.SERVER_NODE] + tc.NODES[2:8] + tc.NODES2[0:1] + \
                [tc.CLIENT_NODE]
            
            expected_replacement = tc.NODES[0:2]
            
        elif mode == message.RESPONSE:
            expected_main = [tc.SERVER2_NODE] + \
                [tc.SERVER_NODE] + tc.NODES[2:8] + tc.NODES2[0:1] + \
                [tc.CLIENT_NODE]
            
            expected_replacement = tc.NODES2[1:7] + tc.NODES[1:2]
            
        all_main, all_replacement = self.routing_m.get_all_rnodes()

        for n, expected in zip(all_main, expected_main):
            eq_(n, expected)
        for n, expected in zip(all_replacement, expected_replacement):
            eq_(n, expected)
        eq_(len(all_main), len(expected_main))
        eq_(len(all_replacement), len(expected_replacement))
            

    def test_query(self):
        self.exercise_mock(message.QUERY)
    def test_response(self):
        self.exercise_mock(message.RESPONSE)

            
        
        
    def test_bootstrap(self):
        self.routing_m.do_bootstrap()
        fn_r = message.OutgoingFindNodeResponse(tc.NODES[0].id,
                                                tc.NODES2[0:1])
        fn_r = message.IncomingMsg(fn_r.encode('\0\0'))
        self.querier.on_response_received(fn_r, tc.NODES[0].addr)

    def test_routing_m_mock(self):
        # Just testing interface
        rm = RoutingManagerMock()
        eq_(rm.get_closest_rnodes(tc.TARGET_ID), tc.NODES)


    def test_complete_coverage(self):
        self.routing_m._do_nothing()
        self.routing_m._refresh_now_callback()
