from Tribler.dispersy.tests.dispersytestclass import DispersyTestFunc
from Tribler.dispersy.util import blocking_call_on_reactor_thread
from twisted.internet.defer import inlineCallbacks, returnValue, Deferred
from twisted.internet.task import deferLater
from twisted.internet import reactor
from Tribler.Test.test_as_server import AbstractServer
from Tribler.community.latency.community import LatencyCommunity
import time
import pickle

class LatencyTests(AbstractServer, DispersyTestFunc):
    """
    This class contains various unit tests for the latency community.
    These tests are able to control each message and parse them at will.
    """

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self):
        AbstractServer.setUp(self)

        yield DispersyTestFunc.setUp(self)
        self.node_a, self.node_b = yield self.create_nodes(2)

    def tearDown(self):
        DispersyTestFunc.tearDown(self)
        AbstractServer.tearDown(self)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_send_ping(self):
        yield self.introduce_nodes(self.node_a, self.node_b)
        yield self.node_a.community.send_ping()
        self.assertEqual(len(self.node_a.community.pingtimes),2)

    @blocking_call_on_reactor_thread
    def test_on_ping(self):
        meta = self.node_a.community.get_meta_message(u"ping")
        message = meta.impl(
            authentication=(self.node_a.community.my_member,),
            distribution=(self.node_a.community.claim_global_time(),),
            payload= ('1.2.3.4', 55, '0.56')
        )
        self.node_a.community.on_ping([message])
        self.assertEqual(len(self.node_a.community.pings),1)

    @blocking_call_on_reactor_thread
    def test_on_pong(self):
        meta = self.node_a.community.get_meta_message(u"pong")
        message = meta.impl(
            authentication=(self.node_a.community.my_member,),
            distribution=(self.node_a.community.claim_global_time(),),
            payload= ('1.2.3.4', 55, '0.56')
        )
        self.node_a.community.pingtimes[('1.2.3.4',55)] = time.time()
        self.node_a.community.on_pong([message])
        self.assertEqual(len(self.node_a.community.pongs),1)
        self.assertEqual(len(self.node_a.community.latencies),1)

    @blocking_call_on_reactor_thread
    def test_on_request_latencies(self):
        meta = self.node_a.community.get_meta_message(u"request_latencies")
        message = meta.impl(
            authentication=(self.node_a.community.my_member,),
            distribution=(self.node_a.community.claim_global_time(),),
            payload= ('1.2.3.4', 55, 0,[3])
        )
        self.node_a.community.on_request_latencies([message])
        self.assertEqual(len(self.node_a.community.relays),1)

    @blocking_call_on_reactor_thread
    def test_on_response_latencies(self):
        meta = self.node_a.community.get_meta_message(u"response_latencies")
        message = meta.impl(
            authentication=(self.node_a.community.my_member,),
            distribution=(self.node_a.community.claim_global_time(),),
            payload= ('1.2.3.4', 55, pickle.dumps({('2.3.4.5',45): '0.43'}),[])
        )
        self.node_a.community.on_response_latencies([message])
        self.assertEqual(len(self.node_a.community.crawled_latencies),1)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def create_nodes(self, *args, **kwargs):
        nodes = yield super(LatencyTests, self).create_nodes(*args, community_class=LatencyCommunity,
                                                                            memory_database=False, **kwargs)
        for outer in nodes:
            for inner in nodes:
                if outer != inner:
                    outer.send_identity(inner)

        returnValue(nodes)

    @inlineCallbacks
    def introduce_nodes(self, node_a, node_b):
        node_b.community.add_discovered_candidate(node_a.my_candidate)
        node_b.take_step()

        yield self.parse_assert_packets(node_a)  # Introduction request
        yield self.parse_assert_packets(node_b)  # Introduction response
        yield deferLater(reactor, 0.05, lambda: None)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def parse_assert_packets(self, node):
        yield deferLater(reactor, 0.05, lambda: None)
        packets = node.process_packets()
        self.assertIsNotNone(packets)
        yield deferLater(reactor, 0.05, lambda: None)