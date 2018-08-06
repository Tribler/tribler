from Tribler.dispersy.tests.dispersytestclass import DispersyTestFunc
from Tribler.dispersy.util import blocking_call_on_reactor_thread
from twisted.internet.defer import inlineCallbacks, returnValue, Deferred
from twisted.internet.task import deferLater
from twisted.internet import reactor
from Tribler.Test.test_as_server import AbstractServer
from Tribler.community.latency.community import LatencyCommunity
import collections

class LatencyTests(AbstractServer, DispersyTestFunc):
    """
    This class contains various integration tests for the latency community.
    These tests are able to control each message and parse them at will.
    """

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def setUp(self):
        AbstractServer.setUp(self)

        yield DispersyTestFunc.setUp(self)
        self.node_a, self.node_b, self.node_c = yield self.create_nodes(3)

    def tearDown(self):
        DispersyTestFunc.tearDown(self)
        AbstractServer.tearDown(self)

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

    @blocking_call_on_reactor_thread
    def _create_target(self, source, destination):
        target = destination.my_candidate
        target.associate(source._dispersy.get_member(public_key=destination.my_pub_member.public_key))
        return target

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_ping_pong(self):
        yield self.introduce_nodes(self.node_a, self.node_b)
        yield self.node_a.community.send_ping()
        # Parse ping
        yield self.parse_assert_packets(self.node_b)
        # Parse pong
        yield self.parse_assert_packets(self.node_a)
        # Test if pong is received.
        self.assertEqual(len(self.node_a.community.latencies),1)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_crawl_latencies(self):
        yield self.introduce_nodes(self.node_a, self.node_b)

        stored_latencies = collections.OrderedDict()
        stored_latencies[('1.2.3.4',56)] = "0.562"
        stored_latencies[('1.2.3.4',80)] = "0.235"
        self.node_b.community.latencies = stored_latencies
        yield self.node_a.community.crawl_latencies()
        # Parse crawl request
        yield self.parse_assert_packets(self.node_b)
        # Parse crawl response
        yield self.parse_assert_packets(self.node_a)
        # Test whether latencies are received.
        self.assertEqual(len(self.node_a.community.crawled_latencies), 2)

    @blocking_call_on_reactor_thread
    @inlineCallbacks
    def test_crawl_latencies_3(self):
        yield self.introduce_nodes(self.node_a, self.node_b)
        yield self.introduce_nodes(self.node_b, self.node_c)
        stored_latencies_b = collections.OrderedDict()
        stored_latencies_b[('1.2.3.4',56)] = "0.562"
        stored_latencies_b[('1.2.3.4',80)] = "0.235"
        self.node_b.community.latencies = stored_latencies_b
        stored_latencies_c = collections.OrderedDict()
        stored_latencies_c[('1.2.3.4',42)] = "0.78"
        stored_latencies_c[('1.2.3.4',81)] = "0.98"
        self.node_c.community.latencies = stored_latencies_c
        yield self.node_a.community.crawl_latencies()
        # Parse crawl request in relay node b.
        yield self.parse_assert_packets(self.node_b)
        # Parse latencies response to node a from node b.
        yield self.parse_assert_packets(self.node_a)
        # Parse crawl request in end node c.
        yield self.parse_assert_packets(self.node_c)
        # Parse latencies response to node b. Node b will forward latencies toward node a.
        yield self.parse_assert_packets(self.node_b)
        # Parse latencies response to node a from node c, indirectly send via node b.
        yield self.parse_assert_packets(self.node_a)
        # Test whether latencies are received at node a and not accidently stored on other nodes.
        self.assertEqual(len(self.node_a.community.crawled_latencies), 4)
        self.assertEqual(len(self.node_b.community.crawled_latencies), 0)
        self.assertEqual(len(self.node_c.community.crawled_latencies), 0)

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