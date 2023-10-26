import time
from random import randint
from typing import List
from unittest.mock import Mock

from ipv8.keyvault.crypto import default_eccrypto
from pony.orm import db_session

from tribler.core.components.ipv8.adapters_tests import TriblerMockIPv8, TriblerTestBase
from tribler.core.components.metadata_store.db.store import MetadataStore
from tribler.core.components.metadata_store.remote_query_community.settings import RemoteQueryCommunitySettings
from tribler.core.components.popularity.community.popularity_community import PopularityCommunity
from tribler.core.components.torrent_checker.torrent_checker.torrentchecker_session import HealthInfo
from tribler.core.tests.tools.base_test import MockObject
from tribler.core.utilities.path_util import Path
from tribler.core.utilities.utilities import random_infohash


def _generate_single_checked_torrent(status: str = None) -> HealthInfo:
    """
    Assumptions
    DEAD    -> peers: 0
    POPULAR -> Peers: [101, 1000]
    DEFAULT -> peers: [1, 100]  # alive
    """

    def get_peers_for(health_status):
        if health_status == 'DEAD':
            return 0
        if health_status == 'POPULAR':
            return randint(101, 1000)
        return randint(1, 100)

    return HealthInfo(random_infohash(), seeders=get_peers_for(status), leechers=get_peers_for(status))


def _generate_checked_torrents(count: int, status: str = None) -> List[HealthInfo]:
    return [_generate_single_checked_torrent(status) for _ in range(count)]


class TestPopularityCommunity(TriblerTestBase):
    NUM_NODES = 2

    def setUp(self):
        super().setUp()
        self.count = 0
        self.metadata_store_set = set()
        self.initialize(PopularityCommunity, self.NUM_NODES)

    async def tearDown(self):
        for metadata_store in self.metadata_store_set:
            metadata_store.shutdown()
        await super().tearDown()

    def create_node(self, *args, **kwargs):
        mds = MetadataStore(Path(self.temporary_directory()) / f"{self.count}",
                            Path(self.temporary_directory()),
                            default_eccrypto.generate_key("curve25519"))
        self.metadata_store_set.add(mds)
        torrent_checker = MockObject()
        torrent_checker.torrents_checked = {}

        self.count += 1

        rqc_settings = RemoteQueryCommunitySettings()
        return TriblerMockIPv8("curve25519", PopularityCommunity, metadata_store=mds,
                               torrent_checker=torrent_checker,
                               rqc_settings=rqc_settings
                               )

    @db_session
    def fill_database(self, metadata_store, last_check_now=False):
        for torrent_ind in range(5):
            last_check = int(time.time()) if last_check_now else 0
            metadata_store.TorrentState(
                infohash=str(torrent_ind).encode() * 20, seeders=torrent_ind + 1, last_check=last_check)

    async def init_first_node_and_gossip(self, checked_torrent_info: HealthInfo, deliver_timeout: float = 0.1):
        self.nodes[0].overlay.torrent_checker.torrents_checked[checked_torrent_info.infohash] = checked_torrent_info
        await self.introduce_nodes()

        self.nodes[0].overlay.gossip_random_torrents_health()

        await self.deliver_messages(timeout=deliver_timeout)

    async def test_torrents_health_gossip(self):
        """
        Test whether torrent health information is correctly gossiped around
        """
        checked_torrent_info = HealthInfo(b'a' * 20, seeders=200, leechers=0)
        node0_db = self.nodes[0].overlay.mds.TorrentState
        node1_db2 = self.nodes[1].overlay.mds.TorrentState

        with db_session:
            assert node0_db.select().count() == 0
            assert node1_db2.select().count() == 0

        await self.init_first_node_and_gossip(checked_torrent_info)

        # Check whether node 1 has new torrent health information
        with db_session:
            torrent = node1_db2.select().first()
            assert torrent.infohash == checked_torrent_info.infohash
            assert torrent.seeders == checked_torrent_info.seeders
            assert torrent.leechers == checked_torrent_info.leechers
            assert torrent.last_check == checked_torrent_info.last_check

    def test_get_alive_torrents(self):
        dead_torrents = _generate_checked_torrents(100, 'DEAD')
        popular_torrents = _generate_checked_torrents(100, 'POPULAR')
        alive_torrents = _generate_checked_torrents(100)

        all_checked_torrents = dead_torrents + alive_torrents + popular_torrents
        self.nodes[0].overlay.torrent_checker.torrents_checked.update(
            {health.infohash: health for health in all_checked_torrents})

        actual_alive_torrents = self.nodes[0].overlay.get_alive_checked_torrents()
        assert len(actual_alive_torrents) == len(alive_torrents + popular_torrents)

    async def test_torrents_health_gossip_multiple(self):
        """
        Test whether torrent health information is correctly gossiped around
        """
        dead_torrents = _generate_checked_torrents(100, 'DEAD')
        popular_torrents = _generate_checked_torrents(100, 'POPULAR')
        alive_torrents = _generate_checked_torrents(100)

        all_checked_torrents = dead_torrents + alive_torrents + popular_torrents

        node0_db = self.nodes[0].overlay.mds.TorrentState
        node1_db = self.nodes[1].overlay.mds.TorrentState

        # Given, initially there are no torrents in the database
        with db_session:
            node0_count = node0_db.select().count()
            node1_count = node1_db.select().count()
            assert node0_count == 0
            assert node1_count == 0

        # Setup, node 0 checks some torrents, both dead and alive (including popular ones).
        self.nodes[0].overlay.torrent_checker.torrents_checked.update(
            {health.infohash: health for health in all_checked_torrents})

        # Nodes are introduced
        await self.introduce_nodes()

        # Since on introduction request callback, node asks for popular torrents, we expect that
        # popular torrents are shared by node 0 to node 1.
        with db_session:
            node0_count = node0_db.select().count()
            node1_count = node1_db.select().count()

            assert node0_count == 0  # Nothing received from Node 1 because it hasn't checked anything to share.
            assert node1_count == PopularityCommunity.GOSSIP_POPULAR_TORRENT_COUNT

            node1_db_last_count = node1_count

        # Now, assuming Node 0 gossips random torrents to Node 1 multiple times to simulate periodic nature
        for _ in range(10):
            self.nodes[0].overlay.gossip_random_torrents_health()
            await self.deliver_messages(timeout=0.1)

            # After gossip, Node 1 should have received some random torrents from Node 0.
            # Note that random torrents can also include popular torrents sent during introduction
            # and random torrents sent in earlier gossip since no state is maintained.
            with db_session:
                node0_count = node0_db.select().count()
                node1_count = node1_db.select().count()

                assert node0_count == 0  # Still nothing received from Node 1 because it hasn't checked torrents
                assert node1_count >= node1_db_last_count

                node1_db_last_count = node1_count

    async def test_torrents_health_update(self):
        """
        Test updating the local torrent health information from network
        """
        self.fill_database(self.nodes[1].overlay.mds)

        checked_torrent_info = HealthInfo(b'0' * 20, seeders=200, leechers=0)
        await self.init_first_node_and_gossip(checked_torrent_info, deliver_timeout=0.5)

        # Check whether node 1 has new torrent health information
        with db_session:
            state = self.nodes[1].overlay.mds.TorrentState.get(infohash=b'0' * 20)
            self.assertIsNot(state.last_check, 0)

    async def test_unknown_torrent_query_back(self):
        """
        Test querying sender for metadata upon receiving an unknown torrent
        """

        infohash = b'1' * 20
        with db_session:
            self.nodes[0].overlay.mds.TorrentMetadata(infohash=infohash)
        await self.init_first_node_and_gossip(
            HealthInfo(infohash, seeders=200, leechers=0))
        with db_session:
            assert self.nodes[1].overlay.mds.TorrentMetadata.get()

    async def test_skip_torrent_query_back_for_known_torrent(self):
        # Test that we _don't_ send the query if we already know about the infohash
        infohash = b'1' * 20
        with db_session:
            self.nodes[0].overlay.mds.TorrentMetadata(infohash=infohash)
            self.nodes[1].overlay.mds.TorrentMetadata(infohash=infohash)
        self.nodes[1].overlay.send_remote_select = Mock()
        await self.init_first_node_and_gossip(
            HealthInfo(infohash, seeders=200, leechers=0))
        self.nodes[1].overlay.send_remote_select.assert_not_called()
