from __future__ import absolute_import

import os

from ipv8.keyvault.crypto import default_eccrypto
from ipv8.peer import Peer
from ipv8.test.base import TestBase
from pony.orm import db_session
from six.moves import xrange
from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_node import NEW, COMMITTED
from Tribler.Core.Modules.MetadataStore.serialization import EMPTY_KEY
from Tribler.Core.Modules.MetadataStore.store import MetadataStore
from Tribler.Core.Utilities.random_utils import random_infohash
from Tribler.Test.Core.base_test import MockObject
from Tribler.community.gigachannel.community import GigaChannelCommunity
from Tribler.pyipv8.ipv8.database import database_blob


class TestGigaChannelUnits(TestBase):
    """
    Unit tests for the GigaChannel community which do not need a real Session.
    """

    def setUp(self):
        super(TestGigaChannelUnits, self).setUp()
        self.count = 0
        self.initialize(GigaChannelCommunity, 2)

    def create_node(self, *args, **kwargs):
        metadata_store = MetadataStore(os.path.join(self.temporary_directory(), "%d.db" % self.count),
                                       self.temporary_directory(), default_eccrypto.generate_key(u"curve25519"))
        kwargs['metadata_store'] = metadata_store
        node = super(TestGigaChannelUnits, self).create_node(*args, **kwargs)
        self.count += 1
        return node

    def add_random_torrent(self, metadata_cls, name="test"):
        torrent_metadata = metadata_cls.from_dict({
            "infohash": random_infohash(),
            "title": name,
            "tags": "",
            "size": 1234,
            "status": NEW
        })
        torrent_metadata.sign()

    @inlineCallbacks
    def test_send_random_one_channel(self):
        """
        Test whether sending a single channel with a single torrent to another peer works correctly
        """
        with db_session:
            channel = self.nodes[0].overlay.metadata_store.ChannelMetadata.create_channel("test", "bla")
            self.add_random_torrent(self.nodes[0].overlay.metadata_store.TorrentMetadata)
            channel.commit_channel_torrent()

        self.nodes[0].overlay.send_random_to(Peer(self.nodes[1].my_peer.public_key, self.nodes[1].endpoint.wan_address))

        yield self.deliver_messages(timeout=0.5)

        with db_session:
            self.assertEqual(len(self.nodes[1].overlay.metadata_store.ChannelMetadata.select()), 1)
            channel = self.nodes[1].overlay.metadata_store.ChannelMetadata.select()[:][0]
            self.assertEqual(channel.contents_len, 1)

    @inlineCallbacks
    def test_send_random_multiple_torrents(self):
        """
        Test whether sending a single channel with a multiple torrents to another peer works correctly
        """
        with db_session:
            channel = self.nodes[0].overlay.metadata_store.ChannelMetadata.create_channel("test", "bla")
            for _ in xrange(20):
                self.add_random_torrent(self.nodes[0].overlay.metadata_store.TorrentMetadata)
            channel.commit_channel_torrent()

        self.nodes[0].overlay.send_random_to(Peer(self.nodes[1].my_peer.public_key, self.nodes[1].endpoint.wan_address))

        yield self.deliver_messages(timeout=0.5)

        with db_session:
            self.assertEqual(len(self.nodes[1].overlay.metadata_store.ChannelMetadata.select()), 1)
            channel = self.nodes[1].overlay.metadata_store.ChannelMetadata.select()[:][0]
            self.assertLess(channel.contents_len, 20)

    @inlineCallbacks
    def test_send_and_get_channel_update_back(self):
        """
        Test if sending back information on updated version of a channel works
        """
        with db_session:
            # Add channel to node 0
            channel = self.nodes[0].overlay.metadata_store.ChannelMetadata.create_channel("test", "bla")
            for _ in xrange(20):
                self.add_random_torrent(self.nodes[0].overlay.metadata_store.TorrentMetadata)
            channel.commit_channel_torrent()
            channel_v1_dict = channel.to_dict()
            channel_v1_dict.pop("health")
            self.add_random_torrent(self.nodes[0].overlay.metadata_store.TorrentMetadata)
            channel.commit_channel_torrent()

            # Add the outdated version of the channel to node 1
            self.nodes[1].overlay.metadata_store.ChannelMetadata.from_dict(channel_v1_dict)

        # node1 --outdated_channel--> node0
        self.nodes[1].overlay.send_random_to(Peer(self.nodes[0].my_peer.public_key, self.nodes[0].endpoint.wan_address))

        yield self.deliver_messages(timeout=0.5)

        with db_session:
            self.assertEqual(self.nodes[1].overlay.metadata_store.ChannelMetadata.select()[:][0].timestamp,
                             self.nodes[0].overlay.metadata_store.ChannelMetadata.select()[:][0].timestamp)

    @inlineCallbacks
    def test_gigachannel_search(self, LEGACY=None):
        """
        Scenario: Node 0 is setup with a channel with 20 ubuntu related torrents. Node 1 searches for 'ubuntu' and
        expects to receive some results. The search results are processed by node 1 when it receives and adds to its
        database. Max number of results is 5, so we expect 5 torrents are added the database.
        """
        def mock_notify(overlay, args):
            overlay.notified_results = True
            self.assertTrue("results" in args[0])

        self.nodes[1].overlay.notifier = MockObject()
        self.nodes[1].overlay.notifier.notify = lambda sub, _type, _obj, args: mock_notify(self.nodes[1].overlay, args)

        yield self.introduce_nodes()

        with db_session:
            # add some free-for-all entries
            self.nodes[0].overlay.metadata_store.TorrentMetadata(title="ubuntu legacy", infohash=random_infohash(),
                                                                 public_key=EMPTY_KEY, status=COMMITTED)
            self.nodes[0].overlay.metadata_store.ChannelMetadata(title="ubuntu legacy chan", infohash=random_infohash(),
                                                                 public_key=EMPTY_KEY, status=LEGACY)
            channel = self.nodes[0].overlay.metadata_store.ChannelMetadata.create_channel("ubuntu", "ubuntu")
            for i in xrange(20):
                self.add_random_torrent(self.nodes[0].overlay.metadata_store.TorrentMetadata, name="ubuntu %s" % i)
            channel.commit_channel_torrent()

        # Node 1 has no torrents and searches for 'ubuntu'
        with db_session:
            torrents = self.nodes[1].overlay.metadata_store.TorrentMetadata.select()[:]
            self.assertEqual(len(torrents), 0)
        self.nodes[1].overlay.send_search_request(u'"ubuntu"*')

        yield self.deliver_messages(timeout=0.5)

        with db_session:
            torrents = self.nodes[1].overlay.metadata_store.TorrentMetadata.select()[:]
            self.assertEqual(len(torrents), 5)

            # Only non-legacy FFA torrents should be sent on search
            torrents_ffa = self.nodes[1].overlay.metadata_store.TorrentMetadata.select(
                lambda g: g.public_key == database_blob(EMPTY_KEY))[:]
            self.assertEqual(len(torrents_ffa), 1)
            # Legacy FFA channel should not be sent
            channels_ffa = self.nodes[1].overlay.metadata_store.ChannelMetadata.select(
                lambda g: g.public_key == database_blob(EMPTY_KEY))[:]
            self.assertEqual(len(channels_ffa), 0)
        self.assertTrue(self.nodes[1].overlay.notified_results)

    @inlineCallbacks
    def test_gigachannel_search_reject_stale_result(self):
        """
        Scenario: If two search requests are sent one after another, the response for the first query becomes stale and
        is rejected.
        """
        yield self.introduce_nodes()

        with db_session:
            channel = self.nodes[0].overlay.metadata_store.ChannelMetadata.create_channel("linux", "ubuntu")
            for i in xrange(10):
                self.add_random_torrent(self.nodes[0].overlay.metadata_store.TorrentMetadata, name="ubuntu %s" % i)
            for i in xrange(10):
                self.add_random_torrent(self.nodes[0].overlay.metadata_store.TorrentMetadata, name="debian %s" % i)
            channel.commit_channel_torrent()

        # Assert Node 1 has no previous torrents in the database
        with db_session:
            torrents = self.nodes[1].overlay.metadata_store.TorrentMetadata.select()[:]
            self.assertEqual(len(torrents), 0)

        # Node 1 sent two consecutive queries
        self.nodes[1].overlay.send_search_request(u'"ubuntu"*')
        self.nodes[1].overlay.send_search_request(u'"debian"*')

        yield self.deliver_messages(timeout=0.5)

        # Assert that only the last result is accepted
        with db_session:
            torrents = self.nodes[1].overlay.metadata_store.TorrentMetadata.select()[:]
            self.assertEqual(len(torrents), 5)
            for torrent in torrents:
                self.assertIn("debian", torrent.to_simple_dict()['name'])

    @inlineCallbacks
    def test_gigachannel_search_with_no_result(self):
        """
        Test giga channel search which yields no result
        """
        yield self.introduce_nodes()

        # Both node 0 and node 1 have no torrents in the database
        with db_session:
            torrents = self.nodes[1].overlay.metadata_store.TorrentMetadata.select()[:]
            torrents2 = self.nodes[1].overlay.metadata_store.TorrentMetadata.select()[:]
            self.assertEqual(len(torrents), 0)
            self.assertEqual(len(torrents2), 0)

        # Node 1 searches for 'A ubuntu'
        query = u'"\xc1 ubuntu"*'
        self.nodes[1].overlay.send_search_request(query)

        yield self.deliver_messages(timeout=0.5)

        # Expect no data received in search and nothing processed to the database
        with db_session:
            torrents = self.nodes[1].overlay.metadata_store.TorrentMetadata.select()[:]
            self.assertEqual(len(torrents), 0)
