import sys
import time

from twisted.internet.defer import succeed, Deferred

from Tribler.Test.Core.base_test import MockObject
from Tribler.Test.ipv8_base import TestBase
from Tribler.Test.mocking.ipv8 import MockIPv8
from Tribler.Test.util.ipv8_util import twisted_wrapper
from Tribler.community.dht.community import DHTCommunity
from Tribler.community.dht.routing import Node, distance


class TestDHTCommunity(TestBase):

    def setUp(self):
        super(TestDHTCommunity, self).setUp()
        self.initialize(DHTCommunity, 2)

        self.key = '\x00' * 20
        self.value = 'test'
        self.value_in_store = self.nodes[0].overlay.serialize_value(self.value, sign=False)
        self.signed_in_store = self.nodes[0].overlay.serialize_value(self.value, sign=True)

        now = time.time()
        for node1 in self.nodes:
            node1.overlay.cancel_pending_task('store_my_peer')
            for node2 in self.nodes:
                if node1 == node2:
                    continue
                dht_node1 = Node(node1.my_peer.key, node1.my_peer.address)
                dht_node2 = Node(node2.my_peer.key, node2.my_peer.address)
                node1.overlay.tokens[dht_node2] = (now, node2.overlay.generate_token(dht_node1))

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
        node = yield self.nodes[0].overlay.ping(self.nodes[1].my_peer)
        self.assertEqual(node, self.nodes[1].my_peer)

    @twisted_wrapper
    def test_ping_pong_fail(self):
        yield self.introduce_nodes()
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

        self.nodes[0].overlay.ping_all()
        yield self.deliver_messages()
        self.assertTrue(node1.failed == 0)
        self.assertNotEqual(node1.last_response, 0)

    @twisted_wrapper
    def test_ping_all_skip(self):
        yield self.introduce_nodes()
        bucket = self.nodes[0].overlay.routing_table.trie[u'']
        node1 = bucket.get(self.nodes[1].overlay.my_node_id)
        node1.failed = 1
        node1.last_response = time.time()

        yield self.nodes[0].overlay.ping_all()
        self.assertTrue(node1.failed == 1)

    @twisted_wrapper
    def test_store_value(self):
        yield self.introduce_nodes()
        node = yield self.nodes[0].overlay.store_value(self.key, self.value)
        self.assertIn(self.nodes[1].my_peer, node)
        self.assertEqual(self.nodes[1].overlay.storage.get(self.key), [self.value_in_store])

    @twisted_wrapper
    def test_store_value_fail(self):
        yield self.introduce_nodes()
        self.nodes[1].unload()
        d = self.nodes[0].overlay.store_value(self.key, self.value)
        yield self.deliver_messages()
        self.assertFailure(d, RuntimeError)

    @twisted_wrapper
    def test_find_nodes(self):
        yield self.introduce_nodes()
        nodes = yield self.nodes[0].overlay.find_nodes(self.key)
        self.assertItemsEqual(nodes, [Node(n.my_peer.key.pub().key_to_bin(), n.my_peer.address)
                                      for n in self.nodes[1:]])

    @twisted_wrapper
    def test_find_values(self):
        yield self.introduce_nodes()
        self.nodes[1].overlay.storage.put(self.key, self.value_in_store)
        values = yield self.nodes[0].overlay.find_values(self.key)
        self.assertIn((self.value, None), values)

    @twisted_wrapper
    def test_find_values_signed(self):
        yield self.introduce_nodes()
        self.nodes[1].overlay.storage.put(self.key, self.signed_in_store)
        values = yield self.nodes[0].overlay.find_values(self.key)
        self.assertIn((self.value, self.nodes[0].my_peer.public_key.key_to_bin()), values)

    @twisted_wrapper
    def test_caching(self):
        # Add a third node
        node = MockIPv8(u"curve25519", DHTCommunity)
        self.add_node_to_experiment(node)

        # Sort nodes based on distance to target
        self.nodes.sort(key=lambda n: distance(n.overlay.my_node_id, self.key), reverse=True)

        self.nodes[0].overlay.on_node_discovered(Node(self.nodes[1].my_peer.key,
                                                      self.nodes[1].my_peer.address))
        self.nodes[1].overlay.on_node_discovered(Node(self.nodes[2].my_peer.key,
                                                      self.nodes[2].my_peer.address))

        self.nodes[2].overlay.storage.put(self.key, self.value_in_store)
        yield self.nodes[0].overlay.find_values(self.key)
        yield self.deliver_messages()
        self.assertEqual(self.nodes[1].overlay.storage.get(self.key), [self.value_in_store])

    @twisted_wrapper
    def test_refresh(self):
        yield self.introduce_nodes()
        yield self.deliver_messages()

        bucket = self.nodes[0].overlay.routing_table.get_bucket(self.nodes[1].overlay.my_node_id)
        bucket.last_changed = 0

        mock = MockObject()
        mock.is_called = False

        self.nodes[0].overlay.find_values = lambda *args: setattr(mock, 'is_called', True) or succeed([])
        self.nodes[0].overlay.value_maintenance()
        self.assertNotEqual(bucket.last_changed, 0)
        self.assertTrue(mock.is_called)

        mock.is_called = False
        prev_ts = bucket.last_changed
        self.nodes[0].overlay.value_maintenance()
        self.assertEqual(bucket.last_changed, prev_ts)
        self.assertFalse(mock.is_called)

    @twisted_wrapper
    def test_republish(self):
        yield self.introduce_nodes()
        yield self.deliver_messages()

        bucket = self.nodes[0].overlay.routing_table.get_bucket(self.nodes[1].overlay.my_node_id)
        bucket.last_changed = 0

        mock = MockObject()
        mock.is_called = False

        self.nodes[0].overlay.storage.put(self.key, self.value_in_store)
        self.nodes[0].overlay.storage.items[self.key][0].last_update = 0
        self.nodes[0].overlay._store = lambda *args: setattr(mock, 'is_called', True) or Deferred()
        self.nodes[0].overlay.value_maintenance()
        self.assertTrue(mock.is_called)

        mock.is_called = False
        self.nodes[0].overlay.storage.put(self.key, self.value_in_store)
        self.nodes[0].overlay.storage.items[self.key][0].last_update = sys.maxint
        self.nodes[0].overlay.value_maintenance()
        self.assertFalse(mock.is_called)

    @twisted_wrapper
    def test_token(self):
        dht_node = Node(self.nodes[1].my_peer.key, self.nodes[1].my_peer.address)

        # Since the setup should have already have generated tokens, a direct store should work.
        yield self.introduce_nodes()
        yield self.nodes[0].overlay.store_on_nodes(self.key, [self.value_in_store], [dht_node])
        yield self.deliver_messages()
        self.assertEqual(self.nodes[1].overlay.storage.get(self.key), [self.value_in_store])

        # Without tokens..
        for node in self.nodes:
            node.overlay.tokens.clear()
        self.nodes[1].overlay.storage.items.clear()
        yield self.introduce_nodes()
        d = self.nodes[0].overlay.store_on_nodes(self.key, [self.value_in_store], [dht_node])
        self.assertFailure(d, RuntimeError)
        self.assertEqual(self.nodes[1].overlay.storage.get(self.key), [])

        # With a bad token..
        self.nodes[0].overlay.tokens[dht_node] = 'faketoken'
        yield self.introduce_nodes()
        d = self.nodes[0].overlay.store_on_nodes(self.key, [self.value_in_store], [dht_node])
        yield self.deliver_messages()
        self.assertFailure(d, RuntimeError)
        self.assertEqual(self.nodes[1].overlay.storage.get(self.key), [])


class TestDHTCommunityXL(TestBase):

    def setUp(self):
        super(TestDHTCommunityXL, self).setUp()
        self.initialize(DHTCommunity, 25)
        for node in self.nodes:
            node.overlay.cancel_pending_task('store_peer')
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
        yield self.nodes[0].overlay.store_value(*kv_pair)

        # Check if the closest nodes have now stored the key
        for node in self.get_closest_nodes(kv_pair[0]):
            self.assertTrue(node.overlay.storage.get(kv_pair[0]), kv_pair[1])

        # Store another value under the same key
        yield self.nodes[1].overlay.store_value('\x00' * 20, 'test2', sign=True)

        # Check if we get both values
        values = yield self.nodes[-1].overlay.find_values('\x00' * 20)
        self.assertIn(('test1', None), values)
        self.assertIn(('test2', self.nodes[1].my_peer.public_key.key_to_bin()), values)
