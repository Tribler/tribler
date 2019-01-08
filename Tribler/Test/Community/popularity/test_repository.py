from __future__ import absolute_import

import os
import time

from pony.orm import db_session
from six.moves import xrange
from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Modules.MetadataStore.store import MetadataStore
from Tribler.Test.Core.base_test import TriblerCoreTest
from Tribler.community.popularity.payload import TorrentHealthPayload
from Tribler.community.popularity.repository import ContentRepository
from Tribler.pyipv8.ipv8.keyvault.crypto import default_eccrypto


class TestContentRepository(TriblerCoreTest):

    @inlineCallbacks
    def setUp(self):
        yield super(TestContentRepository, self).setUp()
        self.my_key = default_eccrypto.generate_key(u"curve25519")
        mds = MetadataStore(os.path.join(self.session_base_dir, 'test.db'), self.session_base_dir, self.my_key)
        self.content_repository = ContentRepository(mds)

        # Add some content to the metadata database
        with db_session:
            mds.ChannelMetadata.create_channel('test', 'test')
            for torrent_ind in xrange(5):
                torrent = mds.TorrentMetadata(title='torrent%d' % torrent_ind, infohash=('%d' % torrent_ind) * 20)
                torrent.health.seeders = torrent_ind + 1

    def test_has_get_torrent(self):
        """
        Test fetching a torrent from the metadata store
        """
        self.assertFalse(self.content_repository.get_torrent('9' * 20))
        self.assertTrue(self.content_repository.get_torrent('0' * 20))
        self.assertFalse(self.content_repository.has_torrent('9' * 20))
        self.assertTrue(self.content_repository.has_torrent('0' * 20))
        self.assertFalse(self.content_repository.get_torrent('\x89' * 20))

    @db_session
    def test_get_top_torrents(self):
        """
        Test fetching the top torrents from the metadata store
        """
        torrents = self.content_repository.get_top_torrents()
        self.assertEqual(len(torrents), 5)
        self.assertEqual(torrents[0].health.seeders, 5)

        self.assertEqual(len(self.content_repository.get_top_torrents(limit=1)), 1)

    def test_add_content(self):
        """
        Test adding and removing content works as expected.
        """
        # Initial content queue is zero
        self.assertEqual(self.content_repository.queue_length(), 0, "No item expected in queue initially")

        # Add a sample content and check the size
        torrent = self.content_repository.get_torrent('0' * 20)
        self.content_repository.add_content_to_queue(torrent)
        self.assertEqual(self.content_repository.queue_length(), 1, "One item expected in queue")

        # Pop an item
        content = self.content_repository.pop_content()
        self.assertEqual(content, torrent, "Content should be equal")

        # Check size again
        self.assertEqual(self.content_repository.queue_length(), 0, "No item expected in queue")

    def test_update_torrent_health(self):
        """
        Tests update torrent health.
        """
        fake_torrent_health_payload = TorrentHealthPayload('0' * 20, 10, 4, time.time())
        self.content_repository.update_torrent_health(fake_torrent_health_payload, peer_trust=0)

        with db_session:
            torrent = self.content_repository.get_torrent('0' * 20)
            self.assertEqual(torrent.health.seeders, 10)
            self.assertEqual(torrent.health.leechers, 4)
