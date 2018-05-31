import random
import string

from Tribler.Test.Core.base_test import MockObject
from Tribler.community.popular.community import PopularCommunity, MSG_TORRENT_HEALTH_RESPONSE, MAX_SUBSCRIBERS, \
    MSG_CHANNEL_HEALTH_RESPONSE, ERROR_UNKNOWN_PEER, MSG_POPULAR_CONTENT_SUBSCRIPTION, ERROR_NO_CONTENT, \
    ERROR_UNKNOWN_RESPONSE
from Tribler.community.popular.constants import SEARCH_TORRENT_REQUEST
from Tribler.community.popular.payload import SearchResponseItemPayload
from Tribler.community.popular.repository import TYPE_TORRENT_HEALTH
from Tribler.pyipv8.ipv8.test.base import TestBase
from Tribler.pyipv8.ipv8.test.mocking.ipv8 import MockIPv8
from Tribler.pyipv8.ipv8.test.util import twisted_wrapper


class TestPopularCommunityBase(TestBase):
    NUM_NODES = 2

    def setUp(self):
        super(TestPopularCommunityBase, self).setUp()
        self.initialize(PopularCommunity, self.NUM_NODES)

    def create_node(self, *args, **kwargs):
        def load_random_torrents(limit):
            return [
                ['\xfdC\xf9+V\x11A\xe7QG\xfb\xb1*6\xef\xa5\xaeu\xc2\xe0',
                 random.randint(200, 250), random.randint(1, 10), 1525704192.166107] for _ in range(limit)
            ]

        torrent_db = MockObject()
        torrent_db.getTorrent = lambda *args, **kwargs: None
        torrent_db.updateTorrent = lambda *args, **kwargs: None
        torrent_db.getRecentlyCheckedTorrents = load_random_torrents

        channel_db = MockObject()

        return MockIPv8(u"curve25519", PopularCommunity, torrent_db=torrent_db, channel_db=channel_db)


class MockRepository(object):

    def _random_string(self, size=6, chars=string.ascii_uppercase + string.digits):
        return ''.join(random.choice(chars) for _ in range(size))

    def _random_infohash(self):
        return ''.join(random.choice('0123456789abcdef') for _ in range(20))

    def search_torrent(self, query):
        # sample search response items
        query_str = ' '.join(query)
        sample_items = []
        for _ in range(10):
            infohash = self._random_infohash()
            name = query_str + " " + self._random_string()
            length = random.randint(1000, 9999)
            num_files = random.randint(1, 10)
            category_list = ['video', 'audio']
            creation_date = random.randint(1000000, 111111111)
            seeders = random.randint(10, 200)
            leechers = random.randint(5, 1000)
            cid = self._random_string(size=20)

            sample_items.append(SearchResponseItemPayload(infohash, name, length, num_files, category_list,
                                                          creation_date, seeders, leechers, cid))
        return sample_items

    def search_channels(self, _):
        return []

    def has_torrent(self, _):
        return False

    def cleanup(self):
        pass

    def update_from_search_results(self, results):
        pass

    def get_torrent(self, _):
        return None

    def get_top_torrents(self):
        return []

    def update_from_torrent_search_results(self, search_results):
        pass


class TestPopularCommunity(TestPopularCommunityBase):
    __testing__ = False
    NUM_NODES = 2

    @twisted_wrapper
    def test_subscribe_peers(self):
        """
        Tests subscribing to peers populate publishers and subscribers list.
        """
        yield self.introduce_nodes()
        self.nodes[0].overlay.subscribe_peers()
        yield self.deliver_messages()

        # Node 0 should have a publisher added
        self.assertEqual(len(self.nodes[0].overlay.publishers), 1, "Expected one publisher")
        # Node 1 should have a subscriber added
        self.assertEqual(len(self.nodes[1].overlay.subscribers), 1, "Expected one subscriber")

    def test_unsubscribe_peers(self):
        """
        Tests unsubscribing peer works as expected.
        """
        def send_popular_content_subscribe(my_peer, _, subscribe):
            if not subscribe:
                my_peer.unsubsribe_called += 1

        self.nodes[0].overlay.send_popular_content_subscribe = lambda peer, subscribe: \
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

    @twisted_wrapper
    def test_start(self):
        """
        Tests starting of the community. Peer should start subscribing to other connected peers.
        """
        yield self.introduce_nodes()
        self.nodes[0].overlay.start()
        yield self.deliver_messages()

        # Node 0 should have a publisher added
        self.assertEqual(len(self.nodes[0].overlay.publishers), 1, "Expected one publisher")
        # Node 1 should have a subscriber added
        self.assertEqual(len(self.nodes[1].overlay.subscribers), 1, "Expected one subscriber")

    @twisted_wrapper
    def test_content_publishing(self):
        """
        Tests publishing next available content.
        :return:
        """
        def on_torrent_health_response(peer, source_address, data):
            peer.torrent_health_response_received = True

        self.nodes[0].torrent_health_response_received = False
        self.nodes[0].overlay.decode_map[chr(MSG_TORRENT_HEALTH_RESPONSE)] = lambda source_address, data: \
            on_torrent_health_response(self.nodes[0], source_address, data)

        yield self.introduce_nodes()
        self.nodes[0].overlay.subscribe_peers()
        yield self.deliver_messages()

        # Add something to queue
        health_info = ('a' * 20, random.randint(1, 100), random.randint(1, 10), random.randint(1, 111111))
        self.nodes[1].overlay._queue_content(TYPE_TORRENT_HEALTH, health_info)

        self.nodes[1].overlay._publish_next_content()

        yield self.deliver_messages()

        self.assertTrue(self.nodes[0].torrent_health_response_received, "Expected to receive torrent response")

    @twisted_wrapper
    def test_publish_no_content(self):
        """
        Tests publishing next content if no content is available.
        """
        original_logger = self.nodes[0].overlay.logger
        self.nodes[0].overlay.logger.error = lambda *args, **kw: self.fake_logger_error(self.nodes[0], *args)

        # Assume a subscribers exist
        self.nodes[0].overlay.subscribers = [self.create_node()]
        # No content
        self.nodes[0].overlay.content_repository.pop_content = lambda: (None, None)

        # Try publishing the next available content
        self.nodes[0].no_content = False
        self.nodes[0].overlay._publish_next_content()
        yield self.deliver_messages()

        # Expect no content found to be logged
        self.assertTrue(self.nodes[0].no_content)

        # Restore logger
        self.nodes[0].overlay.logger = original_logger

    @twisted_wrapper
    def test_send_popular_content_subscribe(self):
        """
        Tests sending popular content subscribe request.
        """
        original_logger = self.nodes[0].overlay.logger
        self.nodes[0].overlay.logger.error = lambda *args, **kw: self.fake_logger_error(self.nodes[0], *args)

        self.nodes[0].overlay.broadcast_message = lambda packet, peer: \
            self.fake_broadcast_message(self.nodes[0], packet, peer)

        # Two default peers
        default_peers = [self.create_node() for _ in range(2)]
        # Assuming only one is connected
        self.nodes[0].overlay.get_peers = lambda: default_peers[:1]

        # Case1: Try to send subscribe request to non-connected peer
        self.nodes[0].unknown_peer_found = False
        self.nodes[0].logger_error_called = False
        self.nodes[0].overlay.send_popular_content_subscribe(default_peers[1], subscribe=True)
        yield self.deliver_messages()

        # Expected unknown peer error log
        self.assertTrue(self.nodes[0].logger_error_called)
        self.assertTrue(self.nodes[0].unknown_peer_found)

        # Case2: Try to send subscribe request to connected peer
        self.nodes[0].broadcast_called = False
        self.nodes[0].broadcast_packet_type = None
        self.nodes[0].overlay.send_popular_content_subscribe(default_peers[0], subscribe=True)
        yield self.deliver_messages()

        # Expect peer to be listed in publisher list and message to be sent
        self.assertTrue(default_peers[0] in self.nodes[0].overlay.publishers)
        self.assertTrue(self.nodes[0].broadcast_called, "Should send a subscribe message to the peer")
        self.assertEqual(self.nodes[0].receiver, default_peers[0], "Intended publisher is different")

        # Try unsubscribing now
        self.nodes[0].overlay.send_popular_content_subscribe(default_peers[0], subscribe=False)
        yield self.deliver_messages()

        # peer should no longer be in publisher list
        self.assertTrue(default_peers[0] not in self.nodes[0].overlay.publishers)

        # Restore logger
        self.nodes[0].overlay.logger = original_logger

    @twisted_wrapper
    def test_send_popular_content_subscription(self):
        """
        Tests sending popular content subscription response.
        """
        original_logger = self.nodes[0].overlay.logger
        self.nodes[0].overlay.logger.error = lambda *args, **kw: self.fake_logger_error(self.nodes[0], *args)

        self.nodes[0].overlay.create_message_packet = lambda _type, _payload: \
            self.fake_create_message_packet(self.nodes[0], _type, _payload)
        self.nodes[0].overlay.broadcast_message = lambda packet, peer: \
            self.fake_broadcast_message(self.nodes[0], packet, peer)

        # Two default peers
        default_peers = [self.create_node() for _ in range(2)]
        # Assuming only one is connected
        self.nodes[0].overlay.get_peers = lambda: default_peers[:1]

        # Case1: Try to send subscribe response to non-connected peer
        self.nodes[0].unknown_peer_found = False
        self.nodes[0].logger_error_called = False
        self.nodes[0].overlay.send_popular_content_subscription(default_peers[1], subscribed=True)
        yield self.deliver_messages()

        # Expected unknown peer error log
        self.assertTrue(self.nodes[0].logger_error_called)
        self.assertTrue(self.nodes[0].unknown_peer_found)

        # Case2: Try to send response to the connected peer
        self.nodes[0].broadcast_called = False
        self.nodes[0].broadcast_packet_type = None
        self.nodes[0].overlay.send_popular_content_subscription(default_peers[0], subscribed=True)
        yield self.deliver_messages()

        # Expect message to be sent
        self.assertTrue(self.nodes[0].packet_created, "Create packet failed")
        self.assertEqual(self.nodes[0].packet_type, MSG_POPULAR_CONTENT_SUBSCRIPTION, "Unexpected payload type found")
        self.assertTrue(self.nodes[0].broadcast_called, "Should send a message to the peer")
        self.assertEqual(self.nodes[0].receiver, default_peers[0], "Intended receiver is different")

        # Restore logger
        self.nodes[0].overlay.logger = original_logger

    @twisted_wrapper
    def test_send_torrent_health_response(self):
        """
        Tests sending torrent health response.
        """
        original_logger = self.nodes[0].overlay.logger
        self.nodes[0].overlay.logger.error = lambda *args, **kw: self.fake_logger_error(self.nodes[0], *args)

        self.nodes[0].overlay.create_message_packet = lambda _type, _payload: \
            self.fake_create_message_packet(self.nodes[0], _type, _payload)
        self.nodes[0].overlay.broadcast_message = lambda packet, peer: \
            self.fake_broadcast_message(self.nodes[0], packet, peer)

        # Two default peers
        default_peers = [self.create_node() for _ in range(2)]
        # Assuming only one is connected
        self.nodes[0].overlay.get_peers = lambda: default_peers[:1]

        # Case1: Try to send subscribe response to non-connected peer
        self.nodes[0].unknown_peer_found = False
        self.nodes[0].logger_error_called = False
        payload = MockObject()
        self.nodes[0].overlay.send_torrent_health_response(payload, peer=default_peers[1])
        yield self.deliver_messages()

        # Expected unknown peer error log
        self.assertTrue(self.nodes[0].logger_error_called)
        self.assertTrue(self.nodes[0].unknown_peer_found)

        # Case2: Try to send response to the connected peer
        self.nodes[0].broadcast_called = False
        self.nodes[0].broadcast_packet_type = None
        self.nodes[0].overlay.send_torrent_health_response(payload, peer=default_peers[0])
        yield self.deliver_messages()

        # Expect message to be sent
        self.assertTrue(self.nodes[0].packet_created, "Create packet failed")
        self.assertEqual(self.nodes[0].packet_type, MSG_TORRENT_HEALTH_RESPONSE, "Unexpected payload type found")
        self.assertTrue(self.nodes[0].broadcast_called, "Should send a message to the peer")
        self.assertEqual(self.nodes[0].receiver, default_peers[0], "Intended receiver is different")

        # Restore logger
        self.nodes[0].overlay.logger = original_logger

    @twisted_wrapper
    def test_send_channel_health_response(self):
        """
        Tests sending torrent health response.
        """
        original_logger = self.nodes[0].overlay.logger
        self.nodes[0].overlay.logger.error = lambda *args, **kw: self.fake_logger_error(self.nodes[0], *args)

        self.nodes[0].overlay.create_message_packet = lambda _type, _payload: \
            self.fake_create_message_packet(self.nodes[0], _type, _payload)
        self.nodes[0].overlay.broadcast_message = lambda packet, peer: \
            self.fake_broadcast_message(self.nodes[0], packet, peer)

        # Two default peers
        default_peers = [self.create_node() for _ in range(2)]
        # Assuming only one is connected
        self.nodes[0].overlay.get_peers = lambda: default_peers[:1]

        # Case1: Try to send response to non-connected peer
        self.nodes[0].unknown_peer_found = False
        self.nodes[0].logger_error_called = False
        payload = MockObject()
        self.nodes[0].overlay.send_channel_health_response(payload, peer=default_peers[1])
        yield self.deliver_messages()

        # Expected unknown peer error log
        self.assertTrue(self.nodes[0].logger_error_called)
        self.assertTrue(self.nodes[0].unknown_peer_found)

        # Case2: Try to send response to the connected peer
        self.nodes[0].broadcast_called = False
        self.nodes[0].broadcast_packet_type = None
        self.nodes[0].overlay.send_channel_health_response(payload, peer=default_peers[0])
        yield self.deliver_messages()

        # Expect message to be sent
        self.assertTrue(self.nodes[0].packet_created, "Create packet failed")
        self.assertEqual(self.nodes[0].packet_type, MSG_CHANNEL_HEALTH_RESPONSE, "Unexpected payload type found")
        self.assertTrue(self.nodes[0].broadcast_called, "Should send a message to the peer")
        self.assertEqual(self.nodes[0].receiver, default_peers[0], "Intended receiver is different")

        # Restore logger
        self.nodes[0].overlay.logger = original_logger

    @twisted_wrapper
    def test_on_torrent_health_response_from_unknown_peer(self):
        """
        Tests receiving torrent health response from unknown peer
        """
        original_logger = self.nodes[0].overlay.logger
        self.nodes[0].overlay.logger.error = lambda *args, **kw: self.fake_logger_error(self.nodes[0], *args)

        def fake_unpack_auth():
            mock_auth = MockObject()
            mock_payload = MockObject()
            return mock_auth, None, mock_payload

        def fake_get_peer_from_auth(peer):
            return peer

        self.nodes[0].overlay._ez_unpack_auth = lambda payload_class, data: fake_unpack_auth()
        self.nodes[0].overlay._get_peer_from_auth = lambda auth, address: fake_get_peer_from_auth(self.nodes[1])

        source_address = MockObject()
        data = MockObject()

        self.nodes[0].unknown_response = True
        self.nodes[0].overlay.on_torrent_health_response(source_address, data)
        yield self.deliver_messages()

        self.assertTrue(self.nodes[0].unknown_response)

        # Restore logger
        self.nodes[0].overlay.logger = original_logger

    @twisted_wrapper
    def test_on_popular_content_subscribe_unknown_peer(self):
        """
        Tests receiving torrent health response from unknown peer
        """
        original_logger = self.nodes[0].overlay.logger
        self.nodes[0].overlay.logger.error = lambda *args, **kw: self.fake_logger_error(self.nodes[0], *args)

        def fake_unpack_auth():
            mock_auth = MockObject()
            mock_payload = MockObject()
            mock_payload.subscribe = True
            return mock_auth, None, mock_payload

        def fake_get_peer_from_auth(peer):
            return peer

        def fake_publish_latest_torrents(my_peer, _peer):
            my_peer.publish_latest_torrents_called = True

        self.nodes[0].overlay._publish_latest_torrents = lambda peer: fake_publish_latest_torrents(self.nodes[1], peer)
        self.nodes[0].overlay._ez_unpack_auth = lambda payload_class, data: fake_unpack_auth()
        self.nodes[0].overlay._get_peer_from_auth = lambda auth, address: fake_get_peer_from_auth(self.nodes[1])

        source_address = MockObject()
        data = MockObject()

        self.nodes[0].unknown_peer_found = False
        self.nodes[0].overlay.on_popular_content_subscribe(source_address, data)
        yield self.deliver_messages()

        self.assertTrue(self.nodes[0].unknown_peer_found)

        # Restore logger
        self.nodes[0].overlay.logger = original_logger

    @twisted_wrapper(5)
    def test_on_popular_content_subscribe_ok(self):
        """
        Tests receiving torrent health response from unknown peer
        """
        original_logger = self.nodes[0].overlay.logger
        self.nodes[0].overlay.logger.error = lambda *args, **kw: self.fake_logger_error(self.nodes[0], *args)

        def fake_unpack_auth():
            mock_auth = MockObject()
            mock_payload = MockObject()
            mock_payload.subscribe = True
            return mock_auth, None, mock_payload

        def fake_get_peer_from_auth(peer):
            return peer

        def fake_publish_latest_torrents(my_peer, _peer):
            my_peer.publish_latest_torrents_called = True

        def fake_send_popular_content_subscription(my_peer):
            my_peer.send_content_subscription_called = True

        self.nodes[0].overlay._publish_latest_torrents = lambda peer: fake_publish_latest_torrents(self.nodes[0], peer)
        self.nodes[0].overlay._ez_unpack_auth = lambda payload_class, data: fake_unpack_auth()
        self.nodes[0].overlay._get_peer_from_auth = lambda auth, address: fake_get_peer_from_auth(self.nodes[1])
        self.nodes[0].overlay.send_popular_content_subscription = lambda peer, subscribed: \
            fake_send_popular_content_subscription(self.nodes[1])

        source_address = MockObject()
        data = MockObject()
        self.nodes[0].unknown_peer_found = False
        self.nodes[0].overlay.on_popular_content_subscribe(source_address, data)
        yield self.deliver_messages()

        self.assertFalse(self.nodes[0].unknown_peer_found)
        self.assertTrue(self.nodes[0].publish_latest_torrents_called)

        # Restore logger
        self.nodes[0].overlay.logger = original_logger

    @twisted_wrapper(5)
    def test_search_request_response(self):

        self.nodes[0].overlay.content_repository = MockRepository()
        self.nodes[1].overlay.content_repository = MockRepository()

        yield self.introduce_nodes()
        self.nodes[0].overlay.subscribe_peers()
        yield self.deliver_messages()

        # Create a search request
        query = "ubuntu"
        self.nodes[0].overlay.send_torrent_search_request(query)

        yield self.deliver_messages()

    @twisted_wrapper(5)
    def test_send_content_info_request(self):
        self.nodes[0].overlay.content_repository = MockRepository()
        self.nodes[1].overlay.content_repository = MockRepository()

        yield self.introduce_nodes()
        self.nodes[0].overlay.subscribe_peers()
        yield self.deliver_messages()

        content_type = SEARCH_TORRENT_REQUEST
        request_list = ["ubuntu"]
        self.nodes[0].overlay.send_content_info_request(content_type, request_list, limit=5, peer=None)
        yield self.deliver_messages()

    def fake_logger_error(self, my_peer, *args):
        if ERROR_UNKNOWN_PEER in args[0]:
            my_peer.unknown_peer_found = True
        if ERROR_NO_CONTENT in args[0]:
            my_peer.no_content = True
        if ERROR_UNKNOWN_RESPONSE in args[0]:
            my_peer.unknown_response = True
        my_peer.logger_error_called = True

    def fake_create_message_packet(self, my_peer, _type, _payload):
        my_peer.packet_created = True
        my_peer.packet_type = _type

    def fake_broadcast_message(self, my_peer, _, peer):
        my_peer.broadcast_called = True
        my_peer.receiver = peer

    def test_add_or_ignore_subscriber(self):
        # Add successfully until max subscriber
        for _ in range(MAX_SUBSCRIBERS):
            self.assertTrue(self.nodes[0].overlay.add_or_ignore_subscriber(self.create_node()))
        # Adding anymore subscriber should return false
        self.assertFalse(self.nodes[0].overlay.add_or_ignore_subscriber(self.create_node()))
