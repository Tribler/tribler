from __future__ import absolute_import

import os
import random

from pony.orm import db_session
from six.moves import xrange
from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Modules.MetadataStore.store import MetadataStore
from Tribler.community.popularity.community import PopularityCommunity, MSG_TORRENT_HEALTH_RESPONSE
from Tribler.pyipv8.ipv8.keyvault.crypto import default_eccrypto
from Tribler.pyipv8.ipv8.test.base import TestBase
from Tribler.pyipv8.ipv8.test.mocking.ipv8 import MockIPv8


class TestPopularityCommunity(TestBase):
    NUM_NODES = 2

    def setUp(self):
        super(TestPopularityCommunity, self).setUp()
        self.shared_key = default_eccrypto.generate_key(u"curve25519")
        self.initialize(PopularityCommunity, self.NUM_NODES)

    def create_node(self, *args, **kwargs):
        mds = MetadataStore(os.path.join(self.temporary_directory(), 'test.db'), self.temporary_directory(),
                            self.shared_key)

        # Add some content to the metadata database
        with db_session:
            mds.ChannelMetadata.create_channel('test', 'test')
            for torrent_ind in xrange(5):
                torrent = mds.TorrentMetadata(title='torrent%d' % torrent_ind, infohash=('%d' % torrent_ind) * 20)
                torrent.health.seeders = torrent_ind + 1

        return MockIPv8(u"curve25519", PopularityCommunity, metadata_store=mds)

    @inlineCallbacks
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
        self.nodes[1].overlay.queue_content(health_info)

        self.nodes[1].overlay.publish_next_content()

        yield self.deliver_messages()

        self.assertTrue(self.nodes[0].torrent_health_response_received, "Expected to receive torrent response")

    @inlineCallbacks
    def test_publish_latest_torrents(self):
        """
        Test publishing all latest torrents
        """
        yield self.introduce_nodes()
        self.nodes[1].overlay.subscribe_peers()
        yield self.deliver_messages()

        # Update the health of some torrents
        with db_session:
            torrents = self.nodes[0].overlay.content_repository.get_top_torrents()
            torrents[0].health.seeders = 500

        self.nodes[0].overlay.publish_latest_torrents(self.nodes[1].overlay.my_peer)
        yield self.deliver_messages()

        with db_session:
            torrents = self.nodes[1].overlay.content_repository.get_top_torrents()
            self.assertEqual(torrents[0].health.seeders, 500)
