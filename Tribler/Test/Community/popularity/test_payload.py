import random
import string
from unittest import TestCase

from Tribler.community.popularity.payload import SearchResponsePayload, SearchResponseItemPayload, ContentInfoRequest, \
    Pagination, ContentInfoResponse, ContentSubscription, TorrentHealthPayload, ChannelHealthPayload, \
    TorrentInfoResponsePayload
from Tribler.pyipv8.ipv8.messaging.serialization import Serializer


class TestSerializer(TestCase):

    def setUp(self):
        self.serializer = Serializer()

    def random_string(self, size=6, chars=string.ascii_uppercase + string.digits):
        return ''.join(random.choice(chars) for _ in range(size))

    def random_infohash(self):
        return ''.join(random.choice('0123456789abcdef') for _ in range(20))

    def test_content_subscription(self):
        """ Test serialization/deserialization of Content subscription """
        subscribe = True
        identifier = 123123
        subscription = ContentSubscription(identifier, subscribe)
        serialized = self.serializer.pack_multiple(subscription.to_pack_list())

        # Deserialize and test it
        (deserialized, _) = self.serializer.unpack_multiple(ContentSubscription.format_list, serialized)
        deserialized_subscription = ContentSubscription.from_unpack_list(*deserialized)

        self.assertEqual(deserialized_subscription.identifier, identifier)
        self.assertTrue(deserialized_subscription.subscribe)

    def test_torrent_health_payload(self):
        """ Test serialization/deserialization of Torrent health payload """
        infohash = 'a' * 20
        num_seeders = 10
        num_leechers = 5
        timestamp = 123123123

        health_payload = TorrentHealthPayload(infohash, num_seeders, num_leechers, timestamp)
        serialized = self.serializer.pack_multiple(health_payload.to_pack_list())

        # Deserialize and test it
        (deserialized, _) = self.serializer.unpack_multiple(TorrentHealthPayload.format_list, serialized)
        deserialized_payload = TorrentHealthPayload.from_unpack_list(*deserialized)

        self.assertEqual(infohash, deserialized_payload.infohash)
        self.assertEqual(num_seeders, deserialized_payload.num_seeders)
        self.assertEqual(num_leechers, deserialized_payload.num_leechers)
        self.assertEqual(timestamp, deserialized_payload.timestamp)

    def test_channel_health_payload(self):
        """ Test serialization/deserialization of Channel health payload """
        channel_id = self.random_string(size=20)
        num_votes = 100
        num_torrents = 5
        swarm_size_sum = 20
        timestamp = 123123123

        health_payload = ChannelHealthPayload(channel_id, num_votes, num_torrents, swarm_size_sum, timestamp)
        serialized = self.serializer.pack_multiple(health_payload.to_pack_list())

        # Deserialize and test it
        (deserialized, _) = self.serializer.unpack_multiple(ChannelHealthPayload.format_list, serialized)
        deserialized_payload = ChannelHealthPayload.from_unpack_list(*deserialized)

        self.assertEqual(channel_id, deserialized_payload.channel_id)
        self.assertEqual(num_votes, deserialized_payload.num_votes)
        self.assertEqual(num_torrents, deserialized_payload.num_torrents)
        self.assertEqual(swarm_size_sum, deserialized_payload.swarm_size_sum)
        self.assertEqual(timestamp, deserialized_payload.timestamp)

    def test_torrent_info_response_payload_for_default_values(self):
        """ Test serialization/deserialization of Torrent health info response payload for default values. """
        infohash = 'a' * 20
        name = None
        length = None
        creation_date = None
        num_files = None
        comment = None

        health_payload = TorrentInfoResponsePayload(infohash, name, length, creation_date, num_files, comment)
        serialized = self.serializer.pack_multiple(health_payload.to_pack_list())

        # Deserialize and test it
        (deserialized, _) = self.serializer.unpack_multiple(TorrentInfoResponsePayload.format_list, serialized)
        deserialized_payload = TorrentInfoResponsePayload.from_unpack_list(*deserialized)

        self.assertEqual(infohash, deserialized_payload.infohash)
        self.assertEqual('', deserialized_payload.name)
        self.assertEqual(0, deserialized_payload.length)
        self.assertEqual(0, deserialized_payload.creation_date)
        self.assertEqual(0, deserialized_payload.num_files)
        self.assertEqual('', deserialized_payload.comment)

    def test_search_result_payload_serialization(self):
        """ Test serialization & deserialization of search payload """
        # sample search response items
        sample_items = []
        for index in range(10):
            infohash = self.random_infohash()
            name = self.random_string()
            length = random.randint(1000, 9999)
            num_files = random.randint(1, 10)
            category_list = ['video', 'audio']
            creation_date = random.randint(1000000, 111111111)
            seeders = random.randint(10, 200)
            leechers = random.randint(5, 1000)
            cid = self.random_string(size=20)

            sample_items.append(SearchResponseItemPayload(infohash, name, length, num_files, category_list,
                                                          creation_date, seeders, leechers, cid))

        # Search identifier
        identifier = 111
        response_type = 1

        # Serialize the results
        results = ''
        for item in sample_items:
            results += self.serializer.pack_multiple(item.to_pack_list())
        serialized_results = self.serializer.pack_multiple(
            SearchResponsePayload(identifier, response_type, results).to_pack_list())

        # De-serialize the response payload and check the identifier and get the results
        response_format = SearchResponsePayload.format_list
        (search_results, _) = self.serializer.unpack_multiple(response_format, serialized_results)

        # De-serialize each individual search result items
        item_format = SearchResponseItemPayload.format_list
        (all_items, _) = self.serializer.unpack_multiple_as_list(item_format, search_results[2])
        for index in xrange(len(all_items)):
            response_item = SearchResponseItemPayload.from_unpack_list(*all_items[index])
            sample_item = sample_items[index]

            self.assertEqual(sample_item.infohash, response_item.infohash)
            self.assertEqual(sample_item.name, response_item.name)
            self.assertEqual(sample_item.length, response_item.length)
            self.assertEqual(sample_item.num_files, response_item.num_files)
            self.assertEqual(sample_item.creation_date, response_item.creation_date)
            self.assertEqual(sample_item.category_list, response_item.category_list)
            self.assertEqual(sample_item.seeders, response_item.seeders)
            self.assertEqual(sample_item.leechers, response_item.leechers)
            self.assertEqual(sample_item.cid, response_item.cid)

    def test_pagination(self):
        """ Test if pagination serialization & deserialization works as expected. """
        page_num = 1
        page_size = 10
        max_results = 50
        more = False

        page = Pagination(page_num, page_size, max_results, more)
        serialized_page = page.serialize()

        # Deserialize and test the parameters
        deserialized_page = Pagination.deserialize(serialized_page)
        self.assertEqual(page.page_number, deserialized_page.page_number)
        self.assertEqual(page.page_size, deserialized_page.page_size)
        self.assertEqual(page.max_results, deserialized_page.max_results)
        self.assertEqual(page.more, deserialized_page.more)

    def test_content_info_request(self):
        """ Test serialization & deserialization of content info request """
        identifier = 1
        content_type = 1
        query_list = "ubuntu 18.04".split()
        limit = 10

        # Serialize request
        in_request = ContentInfoRequest(identifier, content_type, query_list, limit)
        serialized_request = self.serializer.pack_multiple(in_request.to_pack_list())

        # Deserialize request and test it
        (deserialized_request, _) = self.serializer.unpack_multiple(ContentInfoRequest.format_list, serialized_request)
        out_request = ContentInfoRequest.from_unpack_list(*deserialized_request)
        self.assertEqual(in_request.identifier, out_request.identifier)
        self.assertEqual(in_request.query_list, out_request.query_list)
        self.assertEqual(in_request.content_type, out_request.content_type)
        self.assertEqual(in_request.limit, out_request.limit)

    def test_content_info_response(self):
        """ Test serialization & deserialization of content info response """
        identifier = 1
        content_type = 1
        response = self.random_string(size=128)
        more = True
        pagination = Pagination(1, 10, 50, more)

        # Serialize request
        in_response = ContentInfoResponse(identifier, content_type, response, pagination)
        serialized_response = self.serializer.pack_multiple(in_response.to_pack_list())

        # Deserialize request and test it
        (deserialized_response, _) = self.serializer.unpack_multiple(ContentInfoResponse.format_list,
                                                                     serialized_response)
        out_request = ContentInfoResponse.from_unpack_list(*deserialized_response)
        self.assertEqual(in_response.identifier, out_request.identifier)
        self.assertEqual(in_response.response, out_request.response)
        self.assertEqual(in_response.content_type, out_request.content_type)
        self.assertEqual(in_response.pagination.page_number, out_request.pagination.page_number)
        self.assertEqual(in_response.pagination.page_size, out_request.pagination.page_size)
        self.assertEqual(in_response.pagination.max_results, out_request.pagination.max_results)
