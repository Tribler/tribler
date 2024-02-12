from __future__ import annotations

import asyncio
import os
import string
import sys
import time
from asyncio import Future
from binascii import hexlify
from operator import attrgetter
from random import choices, randint
from typing import List
from unittest.mock import AsyncMock, Mock, patch

import pytest
from ipv8.keyvault.crypto import default_eccrypto
from ipv8.messaging.payload import IntroductionRequestPayload
from ipv8.messaging.serialization import default_serializer
from ipv8.test.base import TestBase
from ipv8.test.mocking.ipv8 import MockIPv8
from pony.orm import OperationalError, db_session

from tribler.core import notifications
from tribler.core.components.content_discovery.community.content_discovery_community import ContentDiscoveryCommunity
from tribler.core.components.content_discovery.community.payload import PopularTorrentsRequest, SelectResponsePayload, \
    TorrentsHealthPayload, VersionResponse
from tribler.core.components.content_discovery.community.settings import ContentDiscoverySettings
from tribler.core.components.database.db.layers.knowledge_data_access_layer import KnowledgeDataAccessLayer, \
    ResourceType, SHOW_THRESHOLD
from tribler.core.components.database.db.layers.tests.test_knowledge_data_access_layer_base import \
    Resource, TestKnowledgeAccessLayerBase
from tribler.core.components.database.db.orm_bindings.torrent_metadata import LZ4_EMPTY_ARCHIVE, NEW
from tribler.core.components.database.db.serialization import NULL_KEY, REGULAR_TORRENT
from tribler.core.components.database.db.store import MetadataStore
from tribler.core.components.database.db.tribler_database import TriblerDatabase
from tribler.core.components.torrent_checker.torrent_checker.torrent_checker import TorrentChecker
from tribler.core.components.torrent_checker.torrent_checker.torrentchecker_session import HealthInfo
from tribler.core.tests.tools.base_test import MockObject
from tribler.core.utilities.path_util import Path
from tribler.core.utilities.utilities import random_infohash
from tribler.core.version import version_id


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


def random_string():
    return ''.join(choices(string.ascii_uppercase + string.digits, k=100))


def add_random_torrent(metadata_cls, name="test", seeders=None, leechers=None, last_check=None):
    d = {"infohash": random_infohash(), "public_key": NULL_KEY, "title": name, "tags": "", "size": 1234, "status": NEW}
    torrent_metadata = metadata_cls.from_dict(d)
    if seeders:
        torrent_metadata.health.seeders = seeders
    if leechers:
        torrent_metadata.health.leechers = leechers
    if last_check:
        torrent_metadata.health.last_check = last_check
    return torrent_metadata


class TestContentDiscoveryCommunity(TestBase[ContentDiscoveryCommunity]):
    NUM_NODES = 2

    def setUp(self):
        super().setUp()
        self.count = 0
        self.metadata_store_set = set()
        self.initialize(ContentDiscoveryCommunity, self.NUM_NODES)

    async def tearDown(self):
        for metadata_store in self.metadata_store_set:
            metadata_store.shutdown()
        await super().tearDown()

    def create_node(self, settings: ContentDiscoverySettings | None = None, create_dht: bool = False,
                    enable_statistics: bool = False):
        mds = MetadataStore(Path(self.temporary_directory()) / f"{self.count}",
                            Path(self.temporary_directory()),
                            default_eccrypto.generate_key("curve25519"))
        self.metadata_store_set.add(mds)
        torrent_checker = MockObject()
        torrent_checker.torrents_checked = {}

        tribler_db = TriblerDatabase(str(Path(self.temporary_directory()) / "tags.db"))

        self.count += 1

        return MockIPv8("curve25519", ContentDiscoveryCommunity,
                        ContentDiscoverySettings(metadata_store=mds,
                                                 torrent_checker=torrent_checker,
                                                 tribler_db=tribler_db))

    @db_session
    def fill_database(self, metadata_store, last_check_now=False):
        for torrent_ind in range(5):
            last_check = int(time.time()) if last_check_now else 0
            metadata_store.TorrentState(
                infohash=str(torrent_ind).encode() * 20, seeders=torrent_ind + 1, last_check=last_check)

    async def init_first_node_and_gossip(self, checked_torrent_info: HealthInfo, deliver_timeout: float = 0.1):
        self.torrent_checker(0).torrents_checked[checked_torrent_info.infohash] = checked_torrent_info

        await self.introduce_nodes()

        self.overlay(0).gossip_random_torrents_health()

        await self.deliver_messages(timeout=deliver_timeout)

    def metadata_store(self, i: int) -> MetadataStore:
        return self.overlay(i).composition.metadata_store

    def torrent_checker(self, i: int) -> TorrentChecker:
        return self.overlay(i).composition.torrent_checker

    def torrent_metadata(self, i):
        return self.metadata_store(i).TorrentMetadata

    async def test_torrents_health_gossip(self):
        """
        Test whether torrent health information is correctly gossiped around
        """
        checked_torrent_info = HealthInfo(b'a' * 20, seeders=200, leechers=0)

        with db_session:
            assert self.metadata_store(0).TorrentState.select().count() == 0
            assert self.metadata_store(1).TorrentState.select().count() == 0

        await self.init_first_node_and_gossip(checked_torrent_info)

        # Check whether node 1 has new torrent health information
        with db_session:
            torrent = self.metadata_store(1).TorrentState.select().first()
            assert torrent.infohash == checked_torrent_info.infohash
            assert torrent.seeders == checked_torrent_info.seeders
            assert torrent.leechers == checked_torrent_info.leechers
            assert torrent.last_check == checked_torrent_info.last_check

    async def test_torrents_health_gossip_no_checker(self):
        """
        Test whether no torrent health information is spread without a torrent checker.
        """
        self.overlay(0).composition.torrent_checker = None

        with self.assertReceivedBy(1, [], message_filter=[TorrentsHealthPayload]):
            self.overlay(0).gossip_random_torrents_health()
            await self.deliver_messages()

    async def test_torrents_health_gossip_no_live(self):
        """
        Test whether torrent health information is spread when no live torrents are known
        """
        with self.assertReceivedBy(1, [TorrentsHealthPayload], message_filter=[TorrentsHealthPayload]) as received:
            self.overlay(0).gossip_random_torrents_health()
            await self.deliver_messages()
        message, = received

        assert message.random_torrents_length == 0
        assert message.torrents_checked_length == 0

    def test_get_alive_torrents(self):
        dead_torrents = _generate_checked_torrents(100, 'DEAD')
        popular_torrents = _generate_checked_torrents(100, 'POPULAR')
        alive_torrents = _generate_checked_torrents(100)

        all_checked_torrents = dead_torrents + alive_torrents + popular_torrents
        self.torrent_checker(0).torrents_checked.update(
            {health.infohash: health for health in all_checked_torrents})

        actual_alive_torrents = self.overlay(0).get_alive_checked_torrents()
        assert len(actual_alive_torrents) == len(alive_torrents + popular_torrents)

    def test_get_alive_torrents_no_checker(self):
        self.overlay(0).composition.torrent_checker = None

        assert [] == self.overlay(0).get_alive_checked_torrents()

    async def test_torrents_health_gossip_multiple(self):
        """
        Test whether torrent health information is correctly gossiped around
        """
        dead_torrents = _generate_checked_torrents(100, 'DEAD')
        popular_torrents = _generate_checked_torrents(100, 'POPULAR')
        alive_torrents = _generate_checked_torrents(100)

        all_checked_torrents = dead_torrents + alive_torrents + popular_torrents

        # Given, initially there are no torrents in the database
        with db_session:
            node0_count = self.metadata_store(0).TorrentState.select().count()
            node1_count = self.metadata_store(1).TorrentState.select().count()
            assert node0_count == 0
            assert node1_count == 0

        # Setup, node 0 checks some torrents, both dead and alive (including popular ones).
        self.torrent_checker(0).torrents_checked.update({health.infohash: health for health in all_checked_torrents})
        self.overlay(0).gossip_random_torrents_health()
        await self.deliver_messages()

        # Since on introduction request callback, node asks for popular torrents, we expect that
        # popular torrents are shared by node 0 to node 1.
        with db_session:
            node0_count = self.metadata_store(0).TorrentState.select().count()
            node1_count = self.metadata_store(1).TorrentState.select().count()

            assert node0_count == 0  # Nothing received from Node 1 because it hasn't checked anything to share.
            assert node1_count == self.overlay(1).composition.random_torrent_count

            node1_db_last_count = node1_count

        # Now, assuming Node 0 gossips random torrents to Node 1 multiple times to simulate periodic nature
        for _ in range(10):
            self.overlay(0).gossip_random_torrents_health()
            await self.deliver_messages(timeout=0.1)

            # After gossip, Node 1 should have received some random torrents from Node 0.
            # Note that random torrents can also include popular torrents sent during introduction
            # and random torrents sent in earlier gossip since no state is maintained.
            with db_session:
                node0_count = self.metadata_store(0).TorrentState.select().count()
                node1_count = self.metadata_store(1).TorrentState.select().count()

                assert node0_count == 0  # Still nothing received from Node 1 because it hasn't checked torrents
                assert node1_count >= node1_db_last_count

                node1_db_last_count = node1_count

    async def test_torrents_health_update(self):
        """
        Test updating the local torrent health information from network
        """
        self.fill_database(self.metadata_store(1))

        checked_torrent_info = HealthInfo(b'0' * 20, seeders=200, leechers=0)
        await self.init_first_node_and_gossip(checked_torrent_info, deliver_timeout=0.5)

        # Check whether node 1 has new torrent health information
        with db_session:
            state = self.metadata_store(1).TorrentState.get(infohash=b'0' * 20)
            self.assertIsNot(state.last_check, 0)

    async def test_unknown_torrent_query_back(self):
        """
        Test querying sender for metadata upon receiving an unknown torrent
        """

        infohash = b'1' * 20
        with db_session:
            self.metadata_store(0).TorrentMetadata(infohash=infohash)
        await self.init_first_node_and_gossip(
            HealthInfo(infohash, seeders=200, leechers=0))
        with db_session:
            assert self.metadata_store(1).TorrentMetadata.get()

    async def test_skip_torrent_query_back_for_known_torrent(self):
        # Test that we _don't_ send the query if we already know about the infohash
        infohash = b'1' * 20
        with db_session:
            self.metadata_store(0).TorrentMetadata(infohash=infohash)
            self.metadata_store(1).TorrentMetadata(infohash=infohash)
        self.overlay(1).send_remote_select = Mock()

        await self.init_first_node_and_gossip(HealthInfo(infohash, seeders=200, leechers=0))

        self.overlay(1).send_remote_select.assert_not_called()

    async def test_popularity_search(self):
        """
        Test searching several nodes for metadata entries based on title text
        """
        with db_session:
            # Add test metadata to node ID2
            self.torrent_metadata(1)(title="ubuntu torrent", infohash=random_infohash())
            self.torrent_metadata(1)(title="debian torrent", infohash=random_infohash())

        async def assert_response_received_on_search(search_query: dict):
            notifier = Mock()
            self.overlay(0).composition.notifier = {notifications.remote_query_results: notifier}
            self.overlay(0).send_search_request(**search_query)

            await self.deliver_messages()

            notifier.assert_called()

        # Basic search query
        query1 = {"txt_filter": "ubuntu*"}
        await assert_response_received_on_search(query1)

        # Query with deprecated parameters like 'exclude_deleted'
        query2 = {'txt_filter': '"ubuntu*"', 'hide_xxx': '1', 'metadata_type': REGULAR_TORRENT, 'exclude_deleted': '1'}
        await assert_response_received_on_search(query2)

        # Query with unparsed metadata_type
        query3 = {'txt_filter': '"ubuntu*"', 'metadata_type': str(REGULAR_TORRENT)}
        await assert_response_received_on_search(query3)

    def test_version_response_payload(self):
        """
        Check if the version response is correctly serialized.
        """
        version = "v7.10.0"
        platform = "linux"

        version_response = VersionResponse(version, platform)
        serialized = default_serializer.pack_serializable(version_response)
        deserialized, _ = default_serializer.unpack_serializable(VersionResponse, serialized)

        self.assertEqual(version_response.version, version)
        self.assertEqual(version_response.platform, platform)
        self.assertEqual(deserialized.version, version)
        self.assertEqual(deserialized.platform, platform)

    async def test_request_for_version(self):
        """
        Test whether version request is responded well.
        """
        await self.introduce_nodes()

        on_process_version_response_called = Future()

        def on_process_version_response(peer, version, platform):
            self.assertEqual(peer, self.peer(1))
            self.assertEqual(version, version_id)
            self.assertEqual(platform, sys.platform)
            on_process_version_response_called.set_result(True)

        self.overlay(0).process_version_response = on_process_version_response
        self.overlay(0).send_version_request(self.peer(1))

        return await on_process_version_response_called

    def test_search_for_tags_no_db(self):
        # test that in case of missed `tribler_db`, function `search_for_tags` returns None
        self.overlay(0).composition.tribler_db = None
        assert self.overlay(0).search_for_tags(tags=['tag']) is None

    @patch.object(KnowledgeDataAccessLayer, 'get_subjects_intersection')
    def test_search_for_tags_only_valid_tags(self, mocked_get_subjects_intersection: Mock):
        # test that function `search_for_tags` uses only valid tags
        self.overlay(0).search_for_tags(tags=['invalid_tag' * 50, 'valid_tag'])
        mocked_get_subjects_intersection.assert_called_with(
            subjects_type=ResourceType.TORRENT,
            objects={'valid_tag'},
            predicate=ResourceType.TAG,
            case_sensitive=False
        )

    @patch.object(MetadataStore, 'get_entries_threaded', new_callable=AsyncMock)
    async def test_process_rpc_query_no_tags(self, mocked_get_entries_threaded: AsyncMock):
        # test that in case of missed tags, the remote search works like normal remote search
        parameters = {'first': 0, 'infohash_set': None, 'last': 100}
        await self.overlay(0).process_rpc_query(parameters)

        expected_parameters = {'infohash_set': None}
        expected_parameters.update(parameters)
        mocked_get_entries_threaded.assert_called_with(**expected_parameters)

    async def test_process_rpc_query_with_tags(self):
        # This is full test that checked whether search by tags works or not
        #
        # Test assumes that two databases were filled by the following data (TagsDatabase and MDS):
        infohash1 = os.urandom(20)
        infohash2 = os.urandom(20)
        infohash3 = os.urandom(20)

        @db_session
        def fill_tags_database():
            TestKnowledgeAccessLayerBase.add_operation_set(
                self.overlay(0).composition.tribler_db,
                {
                    hexlify(infohash1).decode(): [
                        Resource(predicate=ResourceType.TAG, name='tag1', count=SHOW_THRESHOLD),
                    ],
                    hexlify(infohash2).decode(): [
                        Resource(predicate=ResourceType.TAG, name='tag1', count=SHOW_THRESHOLD - 1),
                    ]
                }
            )

        @db_session
        def fill_mds():
            with db_session:
                def _add(infohash):
                    torrent = {"infohash": infohash, "title": 'title', "tags": "", "size": 1, "status": NEW}
                    self.metadata_store(0).TorrentMetadata.from_dict(torrent)

                _add(infohash1)
                _add(infohash2)
                _add(infohash3)

        fill_tags_database()
        fill_mds()

        # Then we try to query search for three tags: 'tag1', 'tag2', 'tag3'
        parameters = {'first': 0, 'infohash_set': None, 'last': 100, 'tags': ['tag1']}
        with db_session:
            query_results = [r.to_dict() for r in await self.overlay(0).process_rpc_query(parameters)]

        # Expected results: only one infohash (b'infohash1') should be returned.
        result_infohash_list = [r['infohash'] for r in query_results]
        assert result_infohash_list == [infohash1]

    async def test_remote_select(self):
        """
        Test querying metadata entries from a remote machine
        """

        # Fill Node 0 DB with channels and torrents
        with db_session:
            for i in range(20):
                add_random_torrent(
                    self.torrent_metadata(0),
                    name=f"ubuntu {i}",
                    seeders=2 * i,
                    leechers=i,
                    last_check=int(time.time()) + i,
                )

        kwargs_dict = {"txt_filter": "ubuntu*", "metadata_type": [REGULAR_TORRENT]}
        callback = Mock()
        self.nodes[1].overlay.send_remote_select(self.nodes[0].my_peer, **kwargs_dict, processing_callback=callback)

        await self.deliver_messages(timeout=0.5)
        # Test optional response processing callback
        callback.assert_called()

        # All the matching torrent entries should have been sent to Node 1
        with db_session:
            torrents0 = sorted(self.metadata_store(0).get_entries(**kwargs_dict), key=attrgetter('infohash'))
            torrents1 = sorted(self.metadata_store(1).get_entries(**kwargs_dict), key=attrgetter('infohash'))
            self.assertEqual(len(torrents0), len(torrents1))
            self.assertEqual(len(torrents0), 20)
            for t0, t1 in zip(torrents0, torrents1):
                assert t0.health.seeders == t1.health.seeders
                assert t0.health.leechers == t1.health.leechers
                assert t0.health.last_check == t1.health.last_check

        # Test getting empty response for a query
        kwargs_dict = {"txt_filter": "ubuntu*", "origin_id": 352127}
        callback = Mock()
        self.overlay(1).send_remote_select(self.peer(0), **kwargs_dict, processing_callback=callback)
        await self.deliver_messages(timeout=0.5)
        callback.assert_called()

    async def test_remote_select_deprecated(self):
        """
        Test deprecated search keys receiving an empty archive response.
        """
        with self.assertReceivedBy(0, [SelectResponsePayload]) as responses:
            self.overlay(0).send_remote_select(self.peer(1), subscribed=1)
            await self.deliver_messages()
        response, = responses

        assert response.raw_blob == LZ4_EMPTY_ARCHIVE

    @pytest.mark.timeout(10)
    async def test_remote_select_torrents(self):
        """
        Test dropping packets that go over the response limit for a remote select.
        """
        with db_session:
            torrent_infohash = random_infohash()
            self.torrent_metadata(0)(infohash=torrent_infohash, public_key=NULL_KEY, title='title1')

        callback_called = asyncio.Event()
        processing_results = []

        def callback(_, results):
            processing_results.extend(results)
            callback_called.set()

        self.overlay(1).send_remote_select(
            self.peer(0), metadata_type=[REGULAR_TORRENT], infohash=torrent_infohash, processing_callback=callback
        )

        await callback_called.wait()

        assert len(processing_results) == 1
        obj = processing_results[0].md_obj
        assert isinstance(obj, self.metadata_store(1).TorrentMetadata)
        assert obj.title == 'title1'
        assert obj.health.seeders == 0

    async def test_remote_select_packets_limit(self):
        """
        Test dropping packets that go over the response limit for a remote select.
        """
        with db_session:
            for _ in range(0, 100):
                add_random_torrent(self.torrent_metadata(0), name=random_string())

        kwargs_dict = {"metadata_type": [REGULAR_TORRENT]}

        def add_result(request, processing_results):
            add_result.result_count += 1

        add_result.result_count = 0

        expected = [SelectResponsePayload]
        with self.assertReceivedBy(1, expected, message_filter=[SelectResponsePayload]) as received:
            self.overlay(1).send_remote_select(self.peer(0), **kwargs_dict, processing_callback=add_result)
            while len(received) < 11:  # Packet limit + 1
                await self.deliver_messages()
            if len(received) > len(expected):
                expected.extend([SelectResponsePayload] * (len(received) - len(expected)))

        # Give asyncio some breathing room to process all the packets
        while add_result.result_count < 10:
            await asyncio.sleep(0.1)

        assert [] == self.overlay(1).request_cache.get_tasks()  # The list of outstanding requests should be empty
        assert add_result.result_count == 10  # The packet limit is 10

    def test_sanitize_query(self):
        req_response_list = [
            ({"first": None, "last": None}, {"first": 0, "last": 100}),
            ({"first": 123, "last": None}, {"first": 123, "last": 223}),
            ({"first": None, "last": 1000}, {"first": 0, "last": 100}),
            ({"first": 100, "last": None}, {"first": 100, "last": 200}),
            ({"first": 123}, {"first": 123, "last": 223}),
            ({"last": 123}, {"first": 0, "last": 100}),
            ({}, {"first": 0, "last": 100}),
        ]
        for req, resp in req_response_list:
            assert self.overlay(0).sanitize_query(req) == resp

    def test_sanitize_query_binary_fields(self):
        for field in ("infohash", "channel_pk"):
            field_in_b = b'0' * 20
            field_in_hex = hexlify(field_in_b)
            assert self.overlay(0).sanitize_query({field: field_in_hex})[field] == field_in_b

    async def test_unknown_query_attribute(self):
        rqc_node1 = self.nodes[0].overlay
        rqc_node2 = self.nodes[1].overlay

        # only the new attribute
        rqc_node2.send_remote_select(rqc_node1.my_peer, **{'new_attribute': 'some_value'})
        await self.deliver_messages(timeout=0.1)

        # mixed: the old and a new attribute
        rqc_node2.send_remote_select(rqc_node1.my_peer, **{'infohash': b'0' * 20, 'foo': 'bar'})
        await self.deliver_messages(timeout=0.1)

    async def test_process_rpc_query_match_many(self):
        """
        Check if a correct query with a match in our database returns a result.
        """
        with db_session:
            add_random_torrent(self.torrent_metadata(0), name="torrent1")
            add_random_torrent(self.torrent_metadata(0), name="torrent2")

        results = await self.overlay(0).process_rpc_query({})
        self.assertEqual(2, len(results))

        torrent1_md, torrent2_md = results if results[0].title == "torrent1" else results[::-1]
        self.assertEqual("torrent1", torrent1_md.title)
        self.assertEqual("torrent2", torrent2_md.title)

    async def test_process_rpc_query_match_one(self):
        """
        Check if a correct query with one match in our database returns one result.
        """
        with db_session:
            add_random_torrent(self.torrent_metadata(0), name="a torrent")

        results = await self.overlay(0).process_rpc_query({})
        self.assertEqual(1, len(results))

        (torrent_md,) = results
        self.assertEqual("a torrent", torrent_md.title)

    async def test_process_rpc_query_match_none(self):
        """
        Check if a correct query with no match in our database returns no result.
        """
        results = await self.overlay(0).process_rpc_query({})
        self.assertEqual(0, len(results))

    def test_parse_parameters_match_empty_json(self):
        """
        Check if processing an empty request causes a ValueError (JSONDecodeError) to be raised.
        """
        with self.assertRaises(ValueError):
            self.overlay(0).parse_parameters(b'')

    def test_parse_parameters_match_illegal_json(self):
        """
        Check if processing a request with illegal JSON causes a UnicodeDecodeError to be raised.
        """
        with self.assertRaises(UnicodeDecodeError):
            self.overlay(0).parse_parameters(b'{"akey":\x80}')

    async def test_process_rpc_query_match_invalid_json(self):
        """
        Check if processing a request with invalid JSON causes a ValueError to be raised.
        """
        query = b'{"id_":' + b'\x31' * 200 + b'}'
        with self.assertRaises(ValueError):
            parameters = self.overlay(0).parse_parameters(query)
            await self.overlay(0).process_rpc_query(parameters)

    async def test_process_rpc_query_match_invalid_key(self):
        """
        Check if processing a request with invalid flags causes a UnicodeDecodeError to be raised.
        """
        with self.assertRaises(TypeError):
            parameters = self.overlay(0).parse_parameters(b'{"bla":":("}')
            await self.overlay(0).process_rpc_query(parameters)

    async def test_process_rpc_query_no_column(self):
        """
        Check if processing a request with no database columns causes an OperationalError.
        """
        with self.assertRaises(OperationalError):
            parameters = self.overlay(0).parse_parameters(b'{"txt_filter":{"key":"bla"}}')
            await self.overlay(0).process_rpc_query(parameters)

    async def test_remote_query_big_response(self):
        value = os.urandom(10000)
        with db_session:
            add_random_torrent(self.metadata_store(1).TorrentMetadata, name=hexlify(value).decode())

        kwargs_dict = {"metadata_type": [REGULAR_TORRENT]}
        callback = Mock()
        self.overlay(0).send_remote_select(self.peer(1), **kwargs_dict, processing_callback=callback)

        await self.deliver_messages(timeout=0.5)
        # Test optional response processing callback
        callback.assert_called()

        # All the matching torrent entries should have been sent to Node 1
        with db_session:
            torrents0 = self.metadata_store(0).get_entries(**kwargs_dict)
            torrents1 = self.metadata_store(1).get_entries(**kwargs_dict)
            self.assertEqual(len(torrents0), len(torrents1))

    async def test_drop_silent_peer(self):
        kwargs_dict = {"txt_filter": "ubuntu*"}

        with self.overlay(1).request_cache.passthrough():
            # Stop peer 0 from responding
            self.network(1).remove_peer = Mock()
            self.overlay(1).send_remote_select(self.nodes[0].my_peer, **kwargs_dict)
            await asyncio.sleep(0.0)
            # node 0 must have called remove_peer because of the timeout
            self.network(1).remove_peer.assert_called()

    async def test_dont_drop_silent_peer_on_empty_response(self):
        # Test that even in the case of an empty response packet, remove_peer is not called on timeout

        was_called = []

        async def mock_on_remote_select_response(*_, **__):
            was_called.append(True)
            return []

        kwargs_dict = {"txt_filter": "ubuntu*"}
        self.network(1).remove_peer = Mock()
        self.metadata_store(1).process_compressed_mdblob_threaded = mock_on_remote_select_response
        self.overlay(1).send_remote_select(self.peer(0), **kwargs_dict)
        await self.deliver_messages()
        assert was_called  # Positive check to prevent always passing test
        self.network(1).remove_peer.assert_not_called()

    async def test_remote_select_force_eva(self):
        """
        Test requesting usage of EVA for sending multiple smaller entries.
        """
        with db_session:
            for _ in range(0, 10):
                add_random_torrent(self.torrent_metadata(1), name=hexlify(os.urandom(250)).decode())

        kwargs_dict = {"metadata_type": [REGULAR_TORRENT]}

        callback = AsyncMock()
        self.overlay(0).composition.metadata_store.process_compressed_mdblob_threaded = callback

        self.overlay(0).send_remote_select(self.peer(1), **kwargs_dict, force_eva_response=True)

        await self.deliver_messages()

        callback.assert_called()

    async def test_remote_select_force_eva_error(self):
        """
        Test handling of EVA errors.
        """
        with db_session:
            for _ in range(0, 10):
                add_random_torrent(self.torrent_metadata(1), name=hexlify(os.urandom(250)).decode())

        kwargs_dict = {"metadata_type": [REGULAR_TORRENT]}

        callback = AsyncMock()
        self.overlay(0).composition.metadata_store.process_compressed_mdblob_threaded = callback
        await self.overlay(0).eva.shutdown()

        self.overlay(0).send_remote_select(self.peer(1), **kwargs_dict, force_eva_response=True)

        await self.deliver_messages()

        assert not callback.called

    async def test_multiple_parallel_request(self):
        # Peer A has two torrents "foo" and "bar"
        with db_session:
            add_random_torrent(self.torrent_metadata(0), name="foo")
            add_random_torrent(self.torrent_metadata(0), name="bar")

        # Peer B sends two parallel full-text search queries, only one of them should be processed
        callback1 = Mock()
        kwargs1 = {"txt_filter": "foo", "metadata_type": [REGULAR_TORRENT]}
        self.overlay(1).send_remote_select(self.peer(0), **kwargs1, processing_callback=callback1)

        callback2 = Mock()
        kwargs2 = {"txt_filter": "bar", "metadata_type": [REGULAR_TORRENT]}
        self.overlay(1).send_remote_select(self.peer(0), **kwargs2, processing_callback=callback2)

        original_get_entries = MetadataStore.get_entries

        # Add a delay to ensure that the first query is still being processed when the second one arrives
        # (the mds.get_entries() method is a synchronous one and is called from a worker thread)

        def slow_get_entries(self, *args, **kwargs):
            time.sleep(0.1)
            return original_get_entries(self, *args, **kwargs)

        with patch.object(self.overlay(0), 'logger') as logger, \
                patch.object(MetadataStore, 'get_entries', slow_get_entries):
            await self.deliver_messages(timeout=0.5)

        torrents1 = list(self.metadata_store(1).get_entries(**kwargs1))
        torrents2 = list(self.metadata_store(1).get_entries(**kwargs2))

        # Both remote queries should return results to the peer B...
        assert callback1.called and callback2.called
        # ...but one of them should return an empty list, as the database query was not actually executed
        assert bool(torrents1) != bool(torrents2)

        # Check that on peer A there is exactly one warning about an ignored remote query
        warnings = [call.args[0] for call in logger.warning.call_args_list]
        assert len([msg for msg in warnings if msg.startswith('Ignore remote query')]) == 1

    async def test_ping(self):
        """
        Test if the keep-alive message works.
        """
        with self.assertReceivedBy(1, [IntroductionRequestPayload]):
            self.overlay(0).send_ping(self.peer(1))
            await self.deliver_messages()

    async def test_deprecated_popular_torrents_request_no_live(self):
        """
        The new protocol no longer uses PopularTorrentsRequest but still supports it.
        """
        with self.assertReceivedBy(0, [TorrentsHealthPayload]) as received:
            self.overlay(0).ez_send(self.peer(1), PopularTorrentsRequest())
            await self.deliver_messages()
        message, = received

        assert message.random_torrents_length == 0
        assert message.torrents_checked_length == 0
        assert message.random_torrents == []
        assert message.torrents_checked == []

    async def test_deprecated_popular_torrents_request_live(self):
        """
        The new protocol no longer uses PopularTorrentsRequest but still supports it.
        """
        checked_torrent_info = HealthInfo(b'0' * 20, seeders=200, leechers=0)
        self.torrent_checker(1).torrents_checked[checked_torrent_info.infohash] = checked_torrent_info

        with self.assertReceivedBy(0, [TorrentsHealthPayload], message_filter=[TorrentsHealthPayload]) as received:
            self.overlay(0).ez_send(self.peer(1), PopularTorrentsRequest())
            await self.deliver_messages()
        message, = received

        assert message.random_torrents_length == 0
        assert message.torrents_checked_length == 1
        assert message.random_torrents == []
        assert message.torrents_checked[0] == (b'00000000000000000000', 200, 0, message.torrents_checked[0][3])
