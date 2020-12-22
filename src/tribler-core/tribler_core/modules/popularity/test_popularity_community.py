import logging
import time
from random import randint
from types import SimpleNamespace
from unittest.mock import Mock

from ipv8.keyvault.crypto import default_eccrypto
from ipv8.test.base import TestBase
from ipv8.test.mocking.ipv8 import MockIPv8

from pony.orm import db_session

import pytest

from tribler_core.modules.metadata_store.store import MetadataStore
from tribler_core.modules.popularity.popularity_community import PopularityCommunity
from tribler_core.tests.tools.base_test import MockObject
from tribler_core.utilities.path_util import Path
from tribler_core.utilities.random_utils import random_infohash


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
        torrent_checker.get_torrents_checked = lambda: set()

        return MockIPv8(u"curve25519", PopularityCommunity, metadata_store=mds,
                        torrent_checker=torrent_checker)

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
        db1 = self.nodes[0].overlay.mds.TorrentState
        db2 = self.nodes[1].overlay.mds.TorrentState

        with db_session:
            assert db1.select().count() == 0
            assert db2.select().count() == 0

        await self.init_first_node_and_gossip(checked_torrent_info)

        # Check whether node 1 has new torrent health information
        with db_session:
            torrent = db2.select().first()
            assert torrent.infohash == checked_torrent_info[0]
            assert torrent.seeders == checked_torrent_info[1]
            assert torrent.leechers == checked_torrent_info[2]
            assert torrent.last_check == checked_torrent_info[3]

    async def test_torrents_health_update(self):
        """
        Test updating the local torrent health information from network
        """
        self.fill_database(self.nodes[1].overlay.mds)

        checked_torrent_info = (b'0' * 20, 200, 0, int(time.time()))
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
        await self.init_first_node_and_gossip((infohash, 200, 0, int(time.time())))
        with db_session:
            assert self.nodes[1].overlay.mds.TorrentMetadata.get()

    async def test_skip_torrent_query_back_for_known_torrent(self):
        # Test that we _don't_ send the query if we already know about the infohash
        infohash = b'1' * 20
        with db_session:
            self.nodes[0].overlay.mds.TorrentMetadata(infohash=infohash)
            self.nodes[1].overlay.mds.TorrentMetadata(infohash=infohash)
        self.nodes[1].overlay.send_remote_select = Mock()
        await self.init_first_node_and_gossip((infohash, 200, 0, int(time.time())))
        self.nodes[1].overlay.send_remote_select.assert_not_called()


@pytest.mark.asyncio
async def test_select_torrents_to_gossip_small_list():
    torrents = [
        # infohash, seeders, leechers, last_check
        (b'0' * 20, 0, 0, None),
        (b'1' * 20, 1, 0, None),
        (b'1' * 20, 2, 0, None),
    ]

    popular, rand = PopularityCommunity.select_torrents_to_gossip(set(torrents))
    assert torrents[1] in popular
    assert torrents[2] in popular
    assert not rand


@pytest.mark.asyncio
async def test_select_torrents_to_gossip_big_list():
    # torrent structure is (infohash, seeders, leechers, last_check)
    dead_torrents = {(random_infohash(), 0, randint(1, 10), None)
                     for _ in range(10)}

    alive_torrents = {(random_infohash(), randint(1, 10), randint(1, 10), None)
                      for _ in range(10)}

    top5_popular_torrents = {(random_infohash(), randint(11, 100), randint(1, 10), None)
                             for _ in range(PopularityCommunity.GOSSIP_POPULAR_TORRENT_COUNT)}

    all_torrents = dead_torrents | alive_torrents | top5_popular_torrents

    popular, rand = PopularityCommunity.select_torrents_to_gossip(all_torrents)
    assert len(popular) <= PopularityCommunity.GOSSIP_POPULAR_TORRENT_COUNT
    assert popular == top5_popular_torrents

    assert len(rand) <= PopularityCommunity.GOSSIP_RANDOM_TORRENT_COUNT
    assert rand <= alive_torrents


@pytest.mark.asyncio
async def test_no_alive_torrents():
    torrents = {(random_infohash(), 0, randint(1, 10), None)
                for _ in range(10)}

    popular, rand = PopularityCommunity.select_torrents_to_gossip(torrents)
    assert not popular
    assert not rand


# pylint: disable=super-init-not-called
@pytest.mark.asyncio
async def test_gossip_torrents_health_returns():
    class MockPopularityCommunity(PopularityCommunity):
        def __init__(self):
            self.is_ez_send_has_been_called = False
            self.torrent_checker = None
            self.logger = logging.getLogger()

        def gossip_torrents_health(self):
            PopularityCommunity.gossip_torrents_health(self)

        def ez_send(self, peer, *payloads, **kwargs):
            self.is_ez_send_has_been_called = True

        def get_peers(self):
            return [None]

    community = MockPopularityCommunity()

    community.gossip_torrents_health()
    assert not community.torrent_checker
    assert not community.is_ez_send_has_been_called

    community.torrent_checker = SimpleNamespace()
    community.torrent_checker.torrents_checked = None
    community.gossip_torrents_health()
    assert not community.is_ez_send_has_been_called

    community.torrent_checker.torrents_checked = {(b'0' * 20, 0, 0, None),
                                                  (b'1' * 20, 0, 0, None)}

    community.gossip_torrents_health()
    assert not community.is_ez_send_has_been_called

    community.torrent_checker.torrents_checked = {(b'0' * 20, 1, 0, None),
                                                  (b'1' * 20, 1, 0, None)}
    community.gossip_torrents_health()
    assert community.is_ez_send_has_been_called
