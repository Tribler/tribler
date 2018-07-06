import time

from Tribler.Test.ipv8_base import TestBase
from Tribler.Test.mocking.ipv8 import MockIPv8
from Tribler.Test.util.ipv8_util import twisted_wrapper
from Tribler.community.dht.discovery import DHTDiscoveryCommunity
from Tribler.community.dht.routing import Node


class TestDHTDiscoveryCommunity(TestBase):

    def setUp(self):
        super(TestDHTDiscoveryCommunity, self).setUp()
        self.initialize(DHTDiscoveryCommunity, 2)

        now = time.time()
        for node1 in self.nodes:
            node1.overlay.cancel_pending_task('store_peer')
            for node2 in self.nodes:
                if node1 == node2:
                    continue
                dht_node1 = Node(node1.my_peer.key, node1.my_peer.address)
                dht_node2 = Node(node2.my_peer.key, node2.my_peer.address)
                node1.overlay.tokens[dht_node2] = (now, node2.overlay.generate_token(dht_node1))

    def create_node(self):
        return MockIPv8(u"curve25519", DHTDiscoveryCommunity)

    @twisted_wrapper
    def test_store_peer(self):
        yield self.introduce_nodes()
        yield self.nodes[0].overlay.store_peer()
        self.assertIn(self.nodes[0].my_peer.mid, self.nodes[1].overlay.store)
        self.assertIn(self.nodes[0].my_peer.mid, self.nodes[0].overlay.store_for_me)

    @twisted_wrapper
    def test_store_peer_fail(self):
        yield self.introduce_nodes()
        self.nodes[1].unload()
        d = self.nodes[0].overlay.store_peer()
        yield self.deliver_messages()
        self.assertFailure(d, RuntimeError)

    @twisted_wrapper
    def test_connect_peer(self):
        # Add a third node
        node = MockIPv8(u"curve25519", DHTDiscoveryCommunity)
        self.add_node_to_experiment(node)
        yield self.introduce_nodes()

        # Node1 is storing the peer of node0
        self.nodes[1].overlay.store[self.nodes[0].my_peer.mid].append(self.nodes[0].my_peer)
        self.nodes[0].overlay.store_for_me[self.nodes[0].my_peer.mid].append(self.nodes[1].my_peer)

        org_func = self.nodes[1].overlay.create_puncture_request
        def create_puncture_request(*args):
            self.puncture_to = args[1]
            return org_func(*args)
        self.nodes[1].overlay.create_puncture_request = create_puncture_request

        yield self.deliver_messages()
        nodes = yield self.nodes[2].overlay.connect_peer(self.nodes[0].my_peer.mid)
        self.assertEqual(self.puncture_to, self.nodes[2].my_peer.address)
        self.assertIn(self.nodes[0].overlay.my_peer.public_key.key_to_bin(),
                      [n.public_key.key_to_bin() for n in nodes])

    @twisted_wrapper
    def test_connect_peer_fail(self):
        yield self.introduce_nodes()
        self.nodes[1].unload()
        d = self.nodes[0].overlay.connect_peer(self.nodes[1].my_peer.mid)
        yield self.deliver_messages()
        self.assertFailure(d, RuntimeError)

    def test_ping_all(self):
        self.nodes[0].overlay.ping = lambda n: setattr(self, 'pinged', n)
        self.pinged = None

        node1 = Node(self.nodes[1].my_peer.key, self.nodes[1].my_peer.address)
        node1.last_response = time.time()
        node1.last_query = time.time()

        self.nodes[0].overlay.store[node1.mid].append(node1)
        self.nodes[0].overlay.ping_all()
        self.assertIn(node1, self.nodes[0].overlay.store[node1.mid])

        node1.last_query -= 100
        self.nodes[0].overlay.ping_all()
        self.assertNotIn(node1, self.nodes[0].overlay.store[node1.mid])


        self.nodes[0].overlay.store_for_me[node1.mid].append(node1)
        self.nodes[0].overlay.ping_all()
        self.assertEqual(self.pinged, None)
        self.assertIn(node1.mid, self.nodes[0].overlay.store_for_me)

        node1.last_response -= 30
        self.nodes[0].overlay.ping_all()
        self.assertEqual(self.pinged, node1)
        self.assertIn(node1, self.nodes[0].overlay.store_for_me[node1.mid])

        self.pinged = None
        node1.failed = 3
        self.nodes[0].overlay.ping_all()
        self.assertEqual(self.pinged, None)
        self.assertNotIn(node1, self.nodes[0].overlay.store_for_me[node1.mid])
