import random
import string

from Tribler.Test.Core.base_test import MockObject
from Tribler.community.popularity import constants
from Tribler.community.popularity.community import PopularityCommunity, MSG_TORRENT_HEALTH_RESPONSE, \
    MSG_CHANNEL_HEALTH_RESPONSE, ERROR_UNKNOWN_PEER, ERROR_NO_CONTENT, \
    ERROR_UNKNOWN_RESPONSE
from Tribler.community.popularity.constants import SEARCH_TORRENT_REQUEST, MSG_TORRENT_INFO_RESPONSE, MSG_SUBSCRIPTION
from Tribler.community.popularity.payload import SearchResponseItemPayload, TorrentInfoResponsePayload, \
    TorrentHealthPayload, ContentSubscription
from Tribler.community.popularity.repository import TYPE_TORRENT_HEALTH
from Tribler.community.popularity.request import ContentRequest
from Tribler.pyipv8.ipv8.test.base import TestBase
from Tribler.pyipv8.ipv8.test.mocking.ipv8 import MockIPv8
from Tribler.pyipv8.ipv8.test.util import twisted_wrapper


class TestPopularityCommunityBase(TestBase):
    NUM_NODES = 2

    def setUp(self):
        super(TestPopularityCommunityBase, self).setUp()
        self.initialize(PopularityCommunity, self.NUM_NODES)

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

        return MockIPv8(u"curve25519", PopularityCommunity, torrent_db=torrent_db, channel_db=channel_db)


class MockRepository(object):

    def __init__(self):
        super(MockRepository, self).__init__()
        self.sample_torrents = []
        self.setup_torrents()

    def setup_torrents(self):
        for _ in range(10):
            infohash = self._random_infohash()
            name = self._random_string()
            length = random.randint(1000, 9999)
            num_files = random.randint(1, 10)
            category_list = ['video', 'audio']
            creation_date = random.randint(1000000, 111111111)
            seeders = random.randint(10, 200)
            leechers = random.randint(5, 1000)
            cid = self._random_string(size=20)

            self.sample_torrents.append([infohash, name, length, num_files, category_list, creation_date,
                                         seeders, leechers, cid])

    def _random_string(self, size=6, chars=string.ascii_uppercase + string.digits):
        return ''.join(random.choice(chars) for _ in range(size))

    def _random_infohash(self):
        return ''.join(random.choice('0123456789abcdef') for _ in range(20))

    def search_torrent(self, _):
        sample_items = []
        for torrent in self.sample_torrents:
            sample_items.append(SearchResponseItemPayload(*torrent))
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
        torrent = self.sample_torrents[0]
        db_torrent = {'name': torrent[1],
                      'length': torrent[2],
                      'creation_date': torrent[5],
                      'num_files': torrent[3],
                      'comment': ''}
        return db_torrent

    def get_top_torrents(self):
        return self.sample_torrents

    def update_from_torrent_search_results(self, search_results):
        pass


class TestPopularityCommunity(TestPopularityCommunityBase):
    __testing__ = False
    NUM_NODES = 2

    @twisted_wrapper
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

    @twisted_wrapper
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

    @twisted_wrapper(6)
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
        yield self.sleep(constants.PUBLISH_INTERVAL)

        # Node 0 should have a publisher added
        self.assertEqual(len(self.nodes[0].overlay.publishers), 1, "Expected one publisher")
        # Node 1 should have a subscriber added
        self.assertEqual(len(self.nodes[1].overlay.subscribers), 1, "Expected one subscriber")

        self.assertTrue(self.nodes[0].called_refresh_peer_list)
        self.assertTrue(self.nodes[0].called_publish_next_content)

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
        self.nodes[1].overlay.queue_content(TYPE_TORRENT_HEALTH, health_info)

        self.nodes[1].overlay.publish_next_content()

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
        self.nodes[0].overlay.publish_next_content()
        yield self.deliver_messages()

        # Expect no content found to be logged
        self.assertTrue(self.nodes[0].no_content)

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
    def test_send_torrent_info_request_response(self):
        """ Test if torrent info request response works as expected. """
        self.nodes[1].called_send_torrent_info_response = False
        original_send_torrent_info_response = self.nodes[1].overlay.send_torrent_info_response

        def send_torrent_info_response(node, infohash, peer):
            node.called_infohash = infohash
            node.called_peer = peer
            node.called_send_torrent_info_response = True

        self.nodes[1].overlay.send_torrent_info_response = lambda infohash, peer: \
            send_torrent_info_response(self.nodes[1], infohash, peer)

        yield self.introduce_nodes()
        self.nodes[0].overlay.subscribe_peers()
        yield self.deliver_messages()

        infohash = 'a'*20
        self.nodes[0].overlay.send_torrent_info_request(infohash, self.nodes[1].my_peer)
        yield self.deliver_messages()

        self.assertTrue(self.nodes[1].called_send_torrent_info_response)
        self.nodes[1].overlay.send_torrent_info_response = original_send_torrent_info_response

    @twisted_wrapper
    def test_send_content_info_request_response(self):
        """ Test if content info request response works as expected """

        self.nodes[0].overlay.content_repository = MockRepository()
        self.nodes[1].overlay.content_repository = MockRepository()
        self.nodes[1].overlay.publish_latest_torrents = lambda *args, **kwargs: None

        self.nodes[1].called_send_content_info_response = False

        def send_content_info_response(node, peer, content_type):
            node.called_send_content_info_response = True
            node.called_peer = peer
            node.called_content_type = content_type

        self.nodes[1].overlay.send_content_info_response = lambda peer, identifier, content_type, _: \
            send_content_info_response(self.nodes[1], peer, content_type)

        yield self.introduce_nodes()
        self.nodes[0].overlay.subscribe_peers()
        yield self.deliver_messages()

        content_type = SEARCH_TORRENT_REQUEST
        request_list = ['ubuntu']
        self.nodes[0].overlay.send_content_info_request(content_type, request_list, peer=self.nodes[1].my_peer)
        yield self.deliver_messages()

        self.assertTrue(self.nodes[1].called_send_content_info_response)

    @twisted_wrapper
    def test_on_torrent_health_response_from_unknown_peer(self):
        """
        Tests receiving torrent health response from unknown peer
        """
        original_logger = self.nodes[0].overlay.logger
        self.nodes[0].overlay.logger.error = lambda *args, **kw: self.fake_logger_error(self.nodes[0], *args)

        infohash = 'a' * 20
        num_seeders = 10
        num_leechers = 5
        timestamp = 123123123

        payload = TorrentHealthPayload(infohash, num_seeders, num_leechers, timestamp)
        source_address = ('1.1.1.1', 1024)
        data = self.nodes[0].overlay.create_message_packet(MSG_TORRENT_HEALTH_RESPONSE, payload)

        self.nodes[0].unknown_response = False
        self.nodes[0].overlay.on_torrent_health_response(source_address, data)
        yield self.deliver_messages()

        self.assertTrue(self.nodes[0].unknown_response)

        # Restore logger
        self.nodes[0].overlay.logger = original_logger

    @twisted_wrapper
    def test_on_torrent_health_response(self):
        """
        Tests receiving torrent health response from unknown peer
        """
        def fake_update_torrent(peer):
            peer.called_update_torrent = True

        self.nodes[0].overlay.content_repository = MockRepository()
        self.nodes[0].overlay.content_repository.update_torrent_health = lambda payload, peer_trust: \
            fake_update_torrent(self.nodes[0])

        infohash = 'a' * 20
        num_seeders = 10
        num_leechers = 5
        timestamp = 123123123

        payload = TorrentHealthPayload(infohash, num_seeders, num_leechers, timestamp)
        data = self.nodes[1].overlay.create_message_packet(MSG_TORRENT_HEALTH_RESPONSE, payload)

        yield self.introduce_nodes()

        # Add node 1 in publisher list of node 0
        self.nodes[0].overlay.publishers.add(self.nodes[1].my_peer)
        self.nodes[0].overlay.on_torrent_health_response(self.nodes[1].my_peer.address, data)
        yield self.deliver_messages()

        self.assertTrue(self.nodes[0].called_update_torrent)

    @twisted_wrapper
    def test_on_torrent_info_response(self):
        """
        Tests receiving torrent health response.
        """
        def fake_update_torrent_info(peer):
            peer.called_update_torrent = True

        self.nodes[0].overlay.content_repository = MockRepository()
        self.nodes[0].overlay.content_repository.update_torrent_info = lambda payload: \
            fake_update_torrent_info(self.nodes[0])

        infohash = 'a' * 20
        name = "ubuntu"
        length = 100
        creation_date = 123123123
        num_files = 33
        comment = ''

        payload = TorrentInfoResponsePayload(infohash, name, length, creation_date, num_files, comment)
        data = self.nodes[1].overlay.create_message_packet(MSG_TORRENT_INFO_RESPONSE, payload)

        yield self.introduce_nodes()

        # Add node 1 in publisher list of node 0
        self.nodes[0].overlay.publishers.add(self.nodes[1].my_peer)
        self.nodes[0].overlay.on_torrent_info_response(self.nodes[1].my_peer.address, data)
        yield self.deliver_messages()

        self.assertTrue(self.nodes[0].called_update_torrent)

    @twisted_wrapper
    def test_on_torrent_info_response_from_unknown_peer(self):
        """
        Tests receiving torrent health response from unknown peer.
        """

        def fake_update_torrent_info(peer):
            peer.called_update_torrent = True

        self.nodes[0].overlay.content_repository = MockRepository()
        self.nodes[0].overlay.content_repository.update_torrent_info = lambda payload: \
            fake_update_torrent_info(self.nodes[0])

        infohash = 'a' * 20
        name = "ubuntu"
        length = 100
        creation_date = 123123123
        num_files = 33
        comment = ''

        payload = TorrentInfoResponsePayload(infohash, name, length, creation_date, num_files, comment)
        data = self.nodes[1].overlay.create_message_packet(MSG_TORRENT_INFO_RESPONSE, payload)

        yield self.introduce_nodes()

        self.nodes[0].called_update_torrent = False
        self.nodes[0].overlay.on_torrent_info_response(self.nodes[1].my_peer.address, data)
        yield self.deliver_messages()

        self.assertFalse(self.nodes[0].called_update_torrent)

    @twisted_wrapper
    def test_on_subscription_status1(self):
        """
        Tests receiving subscription status.
        """
        subscribe = True
        identifier = 123123123
        payload = ContentSubscription(identifier, subscribe)
        data = self.nodes[1].overlay.create_message_packet(MSG_SUBSCRIPTION, payload)
        # Set the cache request
        self.nodes[0].overlay.request_cache.pop = lambda prefix, identifer: MockObject()

        yield self.introduce_nodes()
        self.assertEqual(len(self.nodes[0].overlay.publishers), 0)

        self.nodes[0].overlay.on_subscription_status(self.nodes[1].my_peer.address, data)
        yield self.deliver_messages()

        self.assertEqual(len(self.nodes[0].overlay.publishers), 1)

    @twisted_wrapper
    def test_on_subscription_status_with_unsubscribe(self):
        """
        Tests receiving subscription status with unsubscribe status.
        """
        yield self.introduce_nodes()
        self.nodes[0].overlay.publishers.add(self.nodes[1].my_peer)
        self.assertEqual(len(self.nodes[0].overlay.publishers), 1)
        # Set the cache request
        self.nodes[0].overlay.request_cache.pop = lambda prefix, identifer: MockObject()

        subscribe = False
        identifier = 123123123
        payload = ContentSubscription(identifier, subscribe)
        data = self.nodes[1].overlay.create_message_packet(MSG_SUBSCRIPTION, payload)

        self.nodes[0].overlay.on_subscription_status(self.nodes[1].my_peer.address, data)
        yield self.deliver_messages()

        self.assertEqual(len(self.nodes[0].overlay.publishers), 0)

    @twisted_wrapper
    def test_search_request_response(self):
        self.nodes[0].overlay.content_repository = MockRepository()
        self.nodes[1].overlay.content_repository = MockRepository()
        self.nodes[1].overlay.publish_latest_torrents = lambda *args, **kwargs: None

        def fake_process_torrent_search_response(peer):
            peer.called_process_torrent_search_response = True

        self.nodes[0].overlay.process_torrent_search_response = lambda query, payload: \
            fake_process_torrent_search_response(self.nodes[0])

        yield self.introduce_nodes()
        self.nodes[0].overlay.subscribe_peers()
        yield self.deliver_messages()

        # Create a search request
        query = "ubuntu"
        self.nodes[0].overlay.send_torrent_search_request(query)

        yield self.deliver_messages()

        self.assertTrue(self.nodes[0].called_process_torrent_search_response)

    @twisted_wrapper
    def test_process_search_response(self):
        self.nodes[0].overlay.content_repository = MockRepository()
        self.nodes[1].overlay.content_repository = MockRepository()
        self.nodes[1].overlay.publish_latest_torrents = lambda *args, **kwargs: None

        def fake_notify(peer, result_dict):
            peer.called_search_result_notify = True
            self.assertEqual(result_dict['keywords'], 'ubuntu')
            self.assertGreater(len(result_dict['results']), 1)

        self.nodes[0].overlay.tribler_session = MockObject()
        self.nodes[0].overlay.tribler_session.notifier = MockObject()
        self.nodes[0].overlay.tribler_session.notifier.notify = lambda signal1, signal2, _, result_dict: \
            fake_notify(self.nodes[0], result_dict)

        yield self.introduce_nodes()
        self.nodes[0].overlay.subscribe_peers()
        yield self.deliver_messages()

        # Create a search request
        query = "ubuntu"
        self.nodes[0].called_search_result_notify = False

        self.nodes[0].overlay.send_torrent_search_request(query)
        yield self.deliver_messages()

        self.assertTrue(self.nodes[0].called_search_result_notify)

    @twisted_wrapper
    def test_send_content_info_request(self):
        self.nodes[0].overlay.content_repository = MockRepository()
        self.nodes[1].overlay.content_repository = MockRepository()
        self.nodes[1].overlay.publish_latest_torrents = lambda *args, **kwargs: None

        self.nodes[0].received_response = False
        self.nodes[0].received_query = None

        def process_torrent_search_response(node, query):
            node.received_response = True
            node.received_query = query

        self.nodes[0].overlay.process_torrent_search_response = lambda query, data: \
            process_torrent_search_response(self.nodes[0], query)

        yield self.introduce_nodes()
        self.nodes[0].overlay.subscribe_peers()
        yield self.deliver_messages()

        content_type = SEARCH_TORRENT_REQUEST
        request_list = ["ubuntu"]
        self.nodes[0].overlay.send_content_info_request(content_type, request_list, limit=5, peer=None)
        yield self.deliver_messages()

        self.assertTrue(self.nodes[0].received_response)
        self.assertEqual(self.nodes[0].received_query, request_list)

    @twisted_wrapper
    def test_send_torrent_info_response(self):
        self.nodes[1].overlay.publish_latest_torrents = lambda *args, **kwargs: None
        self.nodes[0].overlay.content_repository = MockRepository()
        self.nodes[1].overlay.content_repository = MockRepository()

        self.nodes[0].called_on_torrent_info_response = False

        def on_torrent_info_response(node):
            node.called_on_torrent_info_response = True

        self.nodes[0].overlay.decode_map[chr(MSG_TORRENT_INFO_RESPONSE)] = lambda _source_address, _data: \
            on_torrent_info_response(self.nodes[0])

        yield self.introduce_nodes()
        self.nodes[0].overlay.subscribe_peers()
        yield self.deliver_messages()

        infohash = 'a'*20
        self.nodes[1].overlay.send_torrent_info_response(infohash, self.nodes[0].my_peer)
        yield self.deliver_messages()
        self.assertTrue(self.nodes[0].called_on_torrent_info_response)

    @twisted_wrapper
    def test_search_request_timeout(self):
        """
        Test whether the callback is called with an empty list when the search request times out
        """
        ContentRequest.CONTENT_TIMEOUT = 0.1

        self.nodes[0].overlay.content_repository = MockRepository()
        self.nodes[1].overlay.content_repository = MockRepository()
        self.nodes[1].overlay.publish_latest_torrents = lambda *args, **kwargs: None

        yield self.introduce_nodes()
        self.nodes[0].overlay.subscribe_peers()
        yield self.deliver_messages()

        # Make sure that the other node does not respond to our search query
        self.nodes[1].overlay.send_content_info_response = lambda *_, **__: None

        def on_results(results):
            self.assertIsInstance(results, list)
            self.assertFalse(results)

        content_type = SEARCH_TORRENT_REQUEST
        deferred = self.nodes[0].overlay.send_content_info_request(content_type, ["ubuntu"], limit=5, peer=None)
        yield deferred.addCallback(on_results)

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
