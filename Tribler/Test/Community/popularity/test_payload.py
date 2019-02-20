from __future__ import absolute_import

import random
import string
from unittest import TestCase

from Tribler.community.popularity.payload import (ContentSubscription, TorrentHealthPayload, decode_values,
                                                  encode_values)
from Tribler.pyipv8.ipv8.messaging.serialization import Serializer


class TestSerializer(TestCase):

    def setUp(self):
        self.serializer = Serializer()

    def random_string(self, size=6, chars=string.ascii_uppercase + string.digits):
        return ''.join(random.choice(chars) for _ in range(size))

    def random_infohash(self):
        return ''.join(random.choice('0123456789abcdef') for _ in range(20))

    def test_encode_decode(self):
        value_list = [u'\u0432\u0441\u0435\u043c', u'\u043f\u0440\u0438\u0432\u0435\u0442']
        encoded_value = encode_values(value_list)
        decoded_value = decode_values(encoded_value)
        self.assertEqual(value_list, decoded_value)

    def test_content_subscription(self):
        """ Test serialization/deserialization of Content subscription """
        subscribe = True
        identifier = 123123
        subscription = ContentSubscription(identifier, subscribe)
        serialized = self.serializer.pack_multiple(subscription.to_pack_list())[0]

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
        serialized = self.serializer.pack_multiple(health_payload.to_pack_list())[0]

        # Deserialize and test it
        (deserialized, _) = self.serializer.unpack_multiple(TorrentHealthPayload.format_list, serialized)
        deserialized_payload = TorrentHealthPayload.from_unpack_list(*deserialized)

        self.assertEqual(infohash, deserialized_payload.infohash)
        self.assertEqual(num_seeders, deserialized_payload.num_seeders)
        self.assertEqual(num_leechers, deserialized_payload.num_leechers)
        self.assertEqual(timestamp, deserialized_payload.timestamp)
