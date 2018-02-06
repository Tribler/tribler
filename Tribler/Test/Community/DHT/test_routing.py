import time

from Tribler.Test.test_as_server import AbstractServer
from Tribler.pyipv8.ipv8.keyvault.private.libnaclkey import LibNaCLSK
from Tribler.community.dht.routing import Node, Bucket, RoutingTable, \
                                          NODE_STATUS_GOOD, NODE_STATUS_UNKNOWN, NODE_STATUS_BAD


class FakeNode(object):
    def __init__(self, binary_prefix):
        id_binary = int(binary_prefix + '0' * (160 - len(binary_prefix)), 2)
        id_hex = '%x' % id_binary
        id_hex = '0' + id_hex if len(id_hex) % 2 != 0 else id_hex

        self.id = id_hex.decode('hex')
        self.address = ('1.1.1.1', 1)
        self.status = NODE_STATUS_GOOD
        self.failed = 0
        self.rtt = 0


class TestNode(AbstractServer):

    def setUp(self):
        super(TestNode, self).setUp()
        self.key = LibNaCLSK('\x00' * 64)
        self.node = Node(self.key, ('1.1.1.1', 1))

    def test_init(self):
        self.assertEqual(self.node.bucket, None)
        self.assertEqual(self.node.last_response, 0)
        self.assertEqual(self.node.last_query, 0)
        self.assertEqual(self.node.failed, 0)
        self.assertEqual(self.node.id, '8121e3512feb2d7c476ca95985397d9d1836b6da'.decode('hex'))

    def test_status(self):
        self.node.last_response = time.time()
        self.assertEqual(self.node.status, NODE_STATUS_GOOD)

        self.node.last_response = 1
        self.node.last_query = time.time()
        self.assertEqual(self.node.status, NODE_STATUS_GOOD)

        self.node.last_query = 0
        self.assertEqual(self.node.status, NODE_STATUS_UNKNOWN)

        self.node.failed += 3
        self.assertEqual(self.node.status, NODE_STATUS_BAD)

    def test_last_contact(self):
        self.node.last_query = 5
        self.assertEqual(self.node.last_contact, 5)

        self.node.last_response = 10
        self.assertEqual(self.node.last_contact, 10)


class TestBucket(AbstractServer):

    def setUp(self):
        super(TestBucket, self).setUp()
        self.bucket = Bucket('01', max_size=8)

    def test_owns(self):
        pad_and_convert = lambda b: '{:<040X}'.format(int(b.ljust(160, '0'), 2)).decode('hex')
        self.assertTrue(self.bucket.owns(pad_and_convert('01')))
        self.assertTrue(self.bucket.owns(pad_and_convert('010')))
        self.assertFalse(self.bucket.owns(pad_and_convert('00')))
        self.assertFalse(self.bucket.owns(pad_and_convert('11')))

    def test_get(self):
        self.bucket.nodes[1] = 'node'
        self.assertEqual(self.bucket.get(1), 'node')
        self.assertEqual(self.bucket.get(2), None)

    def test_add_(self):
        node = FakeNode('01')
        self.assertTrue(self.bucket.add(node))
        self.assertEqual(self.bucket.get(node.id), node)

    def test_add_fail(self):
        node = FakeNode('11')
        self.assertFalse(self.bucket.add(node))
        self.assertEqual(self.bucket.get(node.id), None)

    def test_add_update(self):
        node1 = FakeNode('01')
        node2 = FakeNode('01')
        node2.address = ('1.2.3.4', 1)
        self.assertEqual(self.bucket.last_changed, 0)
        self.bucket.add(node1)
        self.bucket.add(node2)
        self.assertEqual(self.bucket.get(node1.id), node1)
        self.assertEqual(self.bucket.get(node1.id).address, ('1.2.3.4', 1))
        self.assertNotEqual(self.bucket.last_changed, 0)

    def test_add_full(self):
        self.bucket.max_size = 1
        node1 = FakeNode('011')
        node2 = FakeNode('010')
        self.bucket.add(node1)
        self.bucket.add(node2)
        self.assertEqual(self.bucket.get(node1.id), node1)
        self.assertEqual(self.bucket.get(node2.id), None)

    def test_add_cleanup(self):
        self.bucket.max_size = 1
        node1 = FakeNode('011')
        node2 = FakeNode('010')
        self.bucket.add(node1)
        node1.failed += 3
        self.bucket.add(node2)
        self.assertEqual(self.bucket.get(node1.id), node1)
        self.assertEqual(self.bucket.get(node2.id), None)

    def test_split(self):
        self.bucket.max_size = 1
        node = FakeNode('011')
        self.bucket.add(node)

        b010, b011 = self.bucket.split()
        self.assertIsInstance(b010, Bucket)
        self.assertIsInstance(b011, Bucket)
        self.assertEqual(b010.get(node.id), None)
        self.assertEqual(b010.prefix_id, '010')
        self.assertEqual(b011.get(node.id), node)
        self.assertEqual(b011.prefix_id, '011')

    def test_split_not_full(self):
        self.assertFalse(self.bucket.split())


class TestRoutingTable(AbstractServer):

    def setUp(self):
        super(TestRoutingTable, self).setUp()
        self.my_node = FakeNode('11' * 20)
        self.routing_table = RoutingTable(self.my_node.id)
        self.trie = self.routing_table.trie

    def test_add_single_node(self):
        node = FakeNode('0')
        self.routing_table.add(node)

        self.assertTrue(self.trie[u''].get(node.id))

    def test_add_multiple_nodes(self):
        node1 = FakeNode('00')
        node2 = FakeNode('01')

        self.routing_table.add(node1)
        self.routing_table.add(node2)

        self.assertTrue(self.trie[u''].get(node1.id))
        self.assertTrue(self.trie[u''].get(node2.id))

    def test_add_node_with_bucket_split(self):
        self.trie[u''].max_size = 1

        node1 = FakeNode('0')
        node2 = FakeNode('1')

        self.routing_table.add(node1)
        self.routing_table.add(node2)

        self.assertTrue(self.trie[u'0'].get(node1.id))
        self.assertTrue(self.trie[u'1'].get(node2.id))

    def test_add_node_full(self):
        self.trie[u''].max_size = 1

        node1 = FakeNode('1')
        node2 = FakeNode('00')
        node3 = FakeNode('01')

        self.routing_table.add(node1)
        self.routing_table.add(node2)
        # This time the bucket should not be split. Instead the node should be dropped.
        self.routing_table.add(node3)

        self.assertTrue(self.trie[u'1'].get(node1.id))
        self.assertTrue(self.trie[u'0'].get(node2.id))
        self.assertFalse(self.trie[u'0'].get(node3.id))

    def test_closest_nodes_single_bucket(self):
        node1 = FakeNode('00')
        node2 = FakeNode('10')
        node3 = FakeNode('01')

        self.routing_table.add(node1)
        self.routing_table.add(node2)
        self.routing_table.add(node3)

        closest_nodes = self.routing_table.closest_nodes('\00' * 20)
        self.assertEqual(closest_nodes[0], node1)
        self.assertEqual(closest_nodes[1], node3)
        self.assertEqual(closest_nodes[2], node2)

    def test_closest_nodes_multiple_buckets(self):
        self.trie[u''].max_size = 1

        node1 = FakeNode('11')
        node2 = FakeNode('10')
        node3 = FakeNode('01')

        self.routing_table.add(node1)
        self.routing_table.add(node2)
        self.routing_table.add(node3)

        closest_nodes = self.routing_table.closest_nodes('\00' * 20)
        self.assertEqual(closest_nodes[0], node3)
        self.assertEqual(closest_nodes[1], node2)
        self.assertEqual(closest_nodes[2], node1)

    def test_closest_nodes_no_nodes(self):
        self.assertFalse(self.routing_table.closest_nodes('\00' * 20))
