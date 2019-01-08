from __future__ import absolute_import

from twisted.internet.defer import inlineCallbacks

from Tribler.Test.tools import trial_timeout
from Tribler.community.popularity.constants import PUBLISH_INTERVAL
from Tribler.community.popularity.pubsub import PubSubCommunity
from Tribler.pyipv8.ipv8.test.base import TestBase
from Tribler.pyipv8.ipv8.test.mocking.ipv8 import MockIPv8


class TestPubSubCommunity(TestBase):
    NUM_NODES = 2

    def setUp(self):
        super(TestPubSubCommunity, self).setUp()
        self.initialize(PubSubCommunity, self.NUM_NODES)

    def create_node(self, *args, **kwargs):
        return MockIPv8(u"curve25519", PubSubCommunity)

    @inlineCallbacks
    def test_subscribe_peers(self):
        """
        Tests subscribing to peers populate publishers and subscribers list.
        """
        self.nodes[1].overlay.send_torrent_info_response = lambda infohash, peer: None
        yield self.introduce_nodes()
        self.nodes[0].overlay.subscribe_peers()
        yield self.deliver_messages()

        # Node 0 should have a publisher added
        self.assertGreater(len(self.nodes[0].overlay.publishers), 0, "Publisher expected")
        # Node 1 should have a subscriber added
        self.assertGreater(len(self.nodes[1].overlay.subscribers), 0, "Subscriber expected")

    @inlineCallbacks
    def test_subscribe_unsubscribe_individual_peers(self):
        """
        Tests subscribing/subscribing an individual peer.
        """
        self.nodes[1].overlay.send_torrent_info_response = lambda infohash, peer: None
        self.nodes[1].overlay.publish_latest_torrents = lambda *args, **kwargs: None

        yield self.introduce_nodes()
        self.nodes[0].overlay.subscribe(self.nodes[1].my_peer, subscribe=True)
        yield self.deliver_messages()

        self.assertEqual(len(self.nodes[0].overlay.publishers), 1, "Expected one publisher")
        self.assertEqual(len(self.nodes[1].overlay.subscribers), 1, "Expected one subscriber")

        self.nodes[0].overlay.subscribe(self.nodes[1].my_peer, subscribe=False)
        yield self.deliver_messages()

        self.assertEqual(len(self.nodes[0].overlay.publishers), 0, "Expected no publisher")
        self.assertEqual(len(self.nodes[1].overlay.subscribers), 0, "Expected no subscriber")

    def test_unsubscribe_multiple_peers(self):
        """
        Tests unsubscribing multiple peers works as expected.
        """

        def send_popular_content_subscribe(my_peer, _, subscribe):
            if not subscribe:
                my_peer.unsubsribe_called += 1

        self.nodes[0].overlay.subscribe = lambda peer, subscribe: \
            send_popular_content_subscribe(self.nodes[0], peer, subscribe)

        # Add some peers
        num_peers = 10
        default_peers = [self.create_node() for _ in range(num_peers)]
        self.nodes[0].overlay.get_peers = lambda: default_peers
        self.assertEqual(len(self.nodes[0].overlay.get_peers()), num_peers)

        # Add some publishers
        for peer in default_peers:
            self.nodes[0].overlay.publishers.add(peer)
        self.assertEqual(len(self.nodes[0].overlay.publishers), num_peers)

        # Unsubscribe all the peers
        self.nodes[0].unsubsribe_called = 0
        self.nodes[0].overlay.unsubscribe_peers()

        # Check if unsubscription was successful
        self.assertEqual(self.nodes[0].unsubsribe_called, num_peers)
        self.assertEqual(len(self.nodes[0].overlay.publishers), 0)

    def test_refresh_peers(self):
        """
        Tests if refresh_peer_list() updates the publishers and subscribers list
        """
        default_peers = [self.create_node() for _ in range(10)]

        for peer in default_peers:
            self.nodes[0].overlay.publishers.add(peer)
            self.nodes[0].overlay.subscribers.add(peer)

        self.nodes[0].overlay.get_peers = lambda: default_peers
        self.assertEqual(len(self.nodes[0].overlay.get_peers()), 10)

        # Remove half of the peers and refresh peer list
        default_peers = default_peers[:5]
        self.nodes[0].overlay.refresh_peer_list()

        # List of publishers and subscribers should be updated
        self.assertEqual(len(self.nodes[0].overlay.get_peers()), 5)
        self.assertEqual(len(self.nodes[0].overlay.subscribers), 5)
        self.assertEqual(len(self.nodes[0].overlay.publishers), 5)

    @trial_timeout(6)
    @inlineCallbacks
    def test_start(self):
        """
        Tests starting of the community. Peer should start subscribing to other connected peers.
        """
        self.nodes[1].overlay.send_torrent_info_response = lambda infohash, peer: None

        def fake_refresh_peer_list(peer):
            peer.called_refresh_peer_list = True

        def fake_publish_next_content(peer):
            peer.called_publish_next_content = True

        self.nodes[0].called_refresh_peer_list = False
        self.nodes[0].called_publish_next_content = False
        self.nodes[0].overlay.refresh_peer_list = lambda: fake_refresh_peer_list(self.nodes[0])
        self.nodes[0].overlay.publish_next_content = lambda: fake_publish_next_content(self.nodes[0])

        yield self.introduce_nodes()
        self.nodes[0].overlay.start()
        yield self.sleep(PUBLISH_INTERVAL)

        # Node 0 should have a publisher added
        self.assertEqual(len(self.nodes[0].overlay.publishers), 1, "Expected one publisher")
        # Node 1 should have a subscriber added
        self.assertEqual(len(self.nodes[1].overlay.subscribers), 1, "Expected one subscriber")

        self.assertTrue(self.nodes[0].called_refresh_peer_list)
        self.assertTrue(self.nodes[0].called_publish_next_content)
