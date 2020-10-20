import time

from ipv8.keyvault.crypto import default_eccrypto
from ipv8.test.base import TestBase
from ipv8.test.mocking.ipv8 import MockIPv8

from pony.orm import db_session

from tribler_common.simpledefs import NTFY

from tribler_core.modules.metadata_store.store import MetadataStore
from tribler_core.modules.popularity.popularity_community import PopularityCommunity
from tribler_core.notifier import Notifier
from tribler_core.tests.tools.base_test import MockObject
from tribler_core.utilities.path_util import Path


class TestPopularityCommunity(TestBase):
    NUM_NODES = 2

    def setUp(self):
        super(TestPopularityCommunity, self).setUp()
        self.count = 0
        self.initialize(PopularityCommunity, self.NUM_NODES)

    def create_node(self, *args, **kwargs):
        mds = MetadataStore(Path(self.temporary_directory()) / ("%d.db" % self.count),
                            Path(self.temporary_directory()),
                            default_eccrypto.generate_key(u"curve25519"))

        torrent_checker = MockObject()
        torrent_checker.torrents_checked = set()

        return MockIPv8(u"curve25519", PopularityCommunity, metadata_store=mds,
                        torrent_checker=torrent_checker, notifier=Notifier())

    @db_session
    def fill_database(self, metadata_store, last_check_now=False):
        for torrent_ind in range(5):
            last_check = int(time.time()) if last_check_now else 0
            metadata_store.TorrentState(
                infohash=str(torrent_ind).encode() * 20, seeders=torrent_ind + 1, last_check=last_check)

    async def init_first_node_and_gossip(self, checked_torrent_info, deliver_timeout=.1):
        self.nodes[0].overlay.torrent_checker.torrents_checked.add(checked_torrent_info)
        await self.introduce_nodes()

        self.nodes[0].overlay.gossip_torrents_health()

        await self.deliver_messages(timeout=deliver_timeout)

    async def test_torrents_health_gossip(self):
        """
        Test whether torrent health information is correctly gossiped around
        """
        checked_torrent_info = (b'a' * 20, 200, 0, int(time.time()))
        await self.init_first_node_and_gossip(checked_torrent_info)

        # Check whether node 1 has new torrent health information
        with db_session:
            self.assertEqual(len(self.nodes[1].overlay.metadata_store.TorrentState.select()), 1)

    async def test_torrents_health_override(self):
        """
        Test whether torrent health information is overridden when it's more fresh
        """
        self.fill_database(self.nodes[1].overlay.metadata_store)

        checked_torrent_info = (b'0' * 20, 200, 0, int(time.time()))
        await self.init_first_node_and_gossip(checked_torrent_info, deliver_timeout=0.5)

        # Check whether node 1 has new torrent health information
        with db_session:
            state = self.nodes[1].overlay.metadata_store.TorrentState.get(infohash=b'0' * 20)
            self.assertIsNot(state.last_check, 0)

    async def test_unknown_torrent_notification(self):
        """Test Popularity Community publish event about receiving an unknown torrent
        """
        notifier = self.nodes[1].overlay.notifier

        class MockRemoteQueryCommunity:
            added_peer = None
            torrent_hash = None

            def on_torrent_state_added(self, peer, torrent_hash):
                self.added_peer = peer
                self.torrent_hash = torrent_hash

        remote_query_community = MockRemoteQueryCommunity()
        notifier.add_observer(NTFY.POPULARITY_COMMUNITY_ADD_UNKNOWN_TORRENT,
                              remote_query_community.on_torrent_state_added)

        assert not remote_query_community.added_peer
        assert not remote_query_community.torrent_hash

        await self.init_first_node_and_gossip((b'1' * 20, 200, 0, int(time.time())))

        assert remote_query_community.added_peer
        assert remote_query_community.torrent_hash
