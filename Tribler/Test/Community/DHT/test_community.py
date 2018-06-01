import sys

from twisted.internet.defer import succeed

from Tribler.Test.ipv8_base import TestBase
from Tribler.Test.mocking.ipv8 import MockIPv8
from Tribler.Test.util.ipv8_util import twisted_wrapper
from Tribler.Test.Core.base_test import MockObject
from Tribler.community.dht.community import DHTCommunity
from Tribler.community.dht.routing import distance, Node


class TestDHTCommunity(TestBase):

    def setUp(self):
        super(TestDHTCommunity, self).setUp()
        self.initialize(DHTCommunity, 2)

    def create_node(self):
        return MockIPv8(u"curve25519", DHTCommunity)

    @twisted_wrapper
    def test_routing_table(self):
        yield self.introduce_nodes()
        yield self.deliver_messages()

        node0_id = self.nodes[0].overlay.my_node_id
        node1_id = self.nodes[1].overlay.my_node_id

        node0_bucket = self.nodes[0].overlay.routing_table.get_bucket(node1_id)
        node1_bucket = self.nodes[1].overlay.routing_table.get_bucket(node0_id)

        self.assertTrue(node0_bucket and node0_bucket.prefix_id == u'')
        self.assertTrue(node1_bucket and node1_bucket.prefix_id == u'')

        self.assertTrue(node1_bucket.get(node0_id))
        self.assertTrue(node0_bucket.get(node1_id))

    @twisted_wrapper
    def test_ping_pong(self):
        yield self.introduce_nodes()
        d = self.nodes[0].overlay.ping(self.nodes[1].my_peer)
        yield self.deliver_messages()
        self.assertEqual((yield d), self.nodes[1].my_peer)

        yield self.nodes[1].unload()
        d = self.nodes[0].overlay.ping(self.nodes[1].my_peer)
        yield self.deliver_messages()
        self.assertFailure(d, RuntimeError)

    @twisted_wrapper
    def test_ping_all(self):
        yield self.introduce_nodes()
        bucket = self.nodes[0].overlay.routing_table.trie[u'']
        node1 = bucket.get(self.nodes[1].overlay.my_node_id)
        node1.failed = 1
        node1.last_response = 0

        yield self.nodes[0].overlay.ping_all()
        self.assertTrue(node1.failed == 0)
        self.assertNotEqual(node1.last_response, 0)

        node1.failed = 1
        yield self.nodes[0].overlay.ping_all()
        self.assertTrue(node1.failed == 1)

    @twisted_wrapper
    def test_store(self):
        yield self.introduce_nodes()
        d = self.nodes[0].overlay.store('\00' * 20, 'test1')
        yield self.deliver_messages()
        self.assertIn(self.nodes[1].my_peer, (yield d))
        self.assertEqual(self.nodes[1].overlay.storage.get('\00' * 20)[0], 'test1')

        yield self.introduce_nodes()
        self.nodes[1].unload()
        d = self.nodes[0].overlay.store('\00' * 20, 'test2')
        yield self.deliver_messages()
        self.assertFailure(d, RuntimeError)
        self.assertEqual(self.nodes[1].overlay.storage.get('\00' * 20)[0], 'test1')

    @twisted_wrapper
    def test_find_nodes(self):
        yield self.introduce_nodes()
        d = self.nodes[0].overlay.find_nodes('\00' * 20)
        yield self.deliver_messages()
        nodes = (yield d)
        self.assertItemsEqual(nodes, [Node(n.my_peer.key.pub().key_to_bin(), n.my_peer.address) for n in self.nodes[1:]])

    @twisted_wrapper
    def test_find_values(self):
        yield self.introduce_nodes()
        self.nodes[1].overlay.storage.put('\00' * 20, 'test', 60)
        d = self.nodes[0].overlay.find_values('\00' * 20)
        yield self.deliver_messages()
        values = (yield d)
        self.assertEqual(values[0], 'test')

    @twisted_wrapper
    def test_move_data(self):
        self.nodes[0].overlay.storage.put(self.nodes[1].overlay.my_node_id, 'test', 60)
        self.nodes[0].overlay.on_node_discovered(Node(self.nodes[1].overlay.my_peer.key,
                                                      self.nodes[1].overlay.my_peer.address))
        yield self.deliver_messages()
        self.assertIn('test', self.nodes[1].overlay.storage.get(self.nodes[1].overlay.my_node_id))

    @twisted_wrapper
    def test_caching(self):
        # Add a third node
        node = MockIPv8(u"curve25519", DHTCommunity)
        self.add_node_to_experiment(node)

        # Sort nodes based on distance to target
        self.nodes.sort(key=lambda n: distance(n.overlay.my_node_id, '\x00' * 20), reverse=True)

        self.nodes[0].overlay.on_node_discovered(Node(self.nodes[1].my_peer.key,
                                                      self.nodes[1].my_peer.address))
        self.nodes[1].overlay.on_node_discovered(Node(self.nodes[2].my_peer.key,
                                                      self.nodes[2].my_peer.address))

        self.nodes[2].overlay.storage.put('\x00' * 20, 'test1', 60)
        yield self.nodes[0].overlay.find_values('\x00' * 20)
        yield self.deliver_messages()

        self.assertEqual(self.nodes[1].overlay.storage.get('\x00' * 20), ['test1'])

    @twisted_wrapper
    def test_maintenance(self):
        yield self.introduce_nodes()
        yield self.deliver_messages()

        bucket = self.nodes[0].overlay.routing_table.get_bucket(self.nodes[1].overlay.my_node_id)
        bucket.last_changed = 0

        mock = MockObject()
        mock.is_called = False

        # Refresh
        self.nodes[0].overlay.find_values = lambda *args: setattr(mock, 'is_called', True)
        self.nodes[0].overlay.maintenance()
        self.assertNotEqual(bucket.last_changed, 0)
        self.assertTrue(mock.is_called)

        mock.is_called = False
        prev_ts = bucket.last_changed
        self.nodes[0].overlay.maintenance()
        self.assertEqual(bucket.last_changed, prev_ts)
        self.assertFalse(mock.is_called)


        # Republish
        mock.is_called = False
        self.nodes[0].overlay.storage.data['\x00' * 20] = [(0, 60, 'test')]
        self.nodes[0].overlay.store = lambda *args: setattr(mock, 'is_called', True)
        self.nodes[0].overlay.maintenance()
        self.assertTrue(mock.is_called)

        mock.is_called = False
        self.nodes[0].overlay.storage.data['\x00' * 20] = [(sys.maxint, 60, 'test')]
        self.nodes[0].overlay.maintenance()
        self.assertFalse(mock.is_called)


class TestDHTCommunityXL(TestBase):

    def setUp(self):
        super(TestDHTCommunityXL, self).setUp()
        self.initialize(DHTCommunity, 25)
        for node in self.nodes:
            node.overlay.ping = lambda _:succeed(None)

    def create_node(self):
        return MockIPv8(u"curve25519", DHTCommunity)

    def get_closest_nodes(self, node_id, max_nodes=8):
        return sorted(self.nodes, key=lambda n: distance(n.overlay.my_node_id, node_id))[:max_nodes]

    @twisted_wrapper
    def test_full_protocol(self):
        # Fill routing tables
        yield self.introduce_nodes()
        yield self.deliver_messages()

        # Store key value pair
        kv_pair = ('\x00' * 20, 'test1')
        yield self.nodes[0].overlay.store(*kv_pair)

        # Check if the closest nodes have now stored the key
        for node in self.get_closest_nodes(kv_pair[0]):
            self.assertTrue(node.overlay.storage.get(kv_pair[0]), kv_pair[1])

        # Store another value under the same key
        yield self.nodes[1].overlay.store('\x00' * 20, 'test2')

        # Check if we get both values
        values = yield self.nodes[-1].overlay.find_values('\x00' * 20)
        self.assertIn('test1', values)
        self.assertIn('test2', values)
