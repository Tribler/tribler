from __future__ import absolute_import

import os

from pony.orm import db_session

from six.moves import xrange

from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_node import NEW
from Tribler.Core.Modules.MetadataStore.store import MetadataStore
from Tribler.Core.Utilities.random_utils import random_infohash
from Tribler.community.gigachannel.community import GigaChannelCommunity
from Tribler.pyipv8.ipv8.keyvault.crypto import default_eccrypto
from Tribler.pyipv8.ipv8.peer import Peer
from Tribler.pyipv8.ipv8.test.base import TestBase


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

    def add_random_torrent(self, metadata_cls):
        torrent_metadata = metadata_cls.from_dict({
            "infohash": random_infohash(),
            "title": "test",
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

        yield self.deliver_messages()

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

        yield self.deliver_messages()

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

        yield self.deliver_messages()

        with db_session:
            self.assertEqual(self.nodes[1].overlay.metadata_store.ChannelMetadata.select()[:][0].timestamp,
                             self.nodes[0].overlay.metadata_store.ChannelMetadata.select()[:][0].timestamp)
