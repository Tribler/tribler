from __future__ import absolute_import

import os
import time

from ipv8.keyvault.crypto import default_eccrypto
from ipv8.test.base import TestBase
from ipv8.test.mocking.ipv8 import MockIPv8

from pony.orm import db_session

from six.moves import xrange

from twisted.internet.defer import inlineCallbacks

from Tribler.Core.Modules.MetadataStore.store import MetadataStore
from Tribler.Test.Core.base_test import MockObject
from Tribler.community.popularity.community import PopularityCommunity


class TestPopularityCommunity(TestBase):
    NUM_NODES = 2

    def setUp(self):
        super(TestPopularityCommunity, self).setUp()
        self.count = 0
        self.initialize(PopularityCommunity, self.NUM_NODES)

    def create_node(self, *args, **kwargs):
        mds = MetadataStore(os.path.join(self.temporary_directory(), "%d.db" % self.count), self.temporary_directory(),
                            default_eccrypto.generate_key(u"curve25519"))

        torrent_checker = MockObject()
        torrent_checker.torrents_checked = set()

        return MockIPv8(u"curve25519", PopularityCommunity, metadata_store=mds, torrent_checker=torrent_checker)

    @db_session
    def fill_database(self, metadata_store, last_check_now=False):
        for torrent_ind in xrange(5):
            last_check = int(time.time()) if last_check_now else 0
            metadata_store.TorrentState(
                infohash=str(torrent_ind).encode() * 20, seeders=torrent_ind + 1, last_check=last_check)

    @inlineCallbacks
    def test_torrents_health_gossip(self):
        """
        Test whether torrent health information is correctly gossiped around
        """
        checked_torrent_info = (b'a' * 20, 200, 0, int(time.time()))
        self.nodes[0].overlay.torrent_checker.torrents_checked.add(checked_torrent_info)
        yield self.introduce_nodes()

        self.nodes[0].overlay.gossip_torrents_health()

        yield self.deliver_messages()

        # Check whether node 1 has new torrent health information
        with db_session:
            self.assertEqual(len(self.nodes[1].overlay.metadata_store.TorrentState.select()), 1)

    @inlineCallbacks
    def test_torrents_health_override(self):
        """
        Test whether torrent health information is overridden when it's more fresh
        """
        self.fill_database(self.nodes[1].overlay.metadata_store)

        checked_torrent_info = (b'0' * 20, 200, 0, int(time.time()))
        self.nodes[0].overlay.torrent_checker.torrents_checked.add(checked_torrent_info)
        yield self.introduce_nodes()

        self.nodes[0].overlay.gossip_torrents_health()

        yield self.deliver_messages(timeout=0.5)

        # Check whether node 1 has new torrent health information
        with db_session:
            state = self.nodes[1].overlay.metadata_store.TorrentState.get(infohash=b'0' * 20)
            self.assertIsNot(state.last_check, 0)
