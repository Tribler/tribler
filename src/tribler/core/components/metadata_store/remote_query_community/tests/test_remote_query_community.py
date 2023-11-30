import asyncio
import random
import string
import time
from asyncio import sleep
from binascii import hexlify, unhexlify
from operator import attrgetter
from os import urandom
from unittest.mock import Mock, patch

import pytest
from ipv8.keyvault.crypto import default_eccrypto
from pony.orm import db_session
from pony.orm.dbapiprovider import OperationalError

from tribler.core.components.ipv8.adapters_tests import TriblerTestBase
from tribler.core.components.metadata_store.db.orm_bindings.torrent_metadata import NEW, LZ4_EMPTY_ARCHIVE
from tribler.core.components.metadata_store.db.serialization import CHANNEL_THUMBNAIL, REGULAR_TORRENT, \
    NULL_KEY
from tribler.core.components.metadata_store.db.store import MetadataStore
from tribler.core.components.metadata_store.remote_query_community.remote_query_community import (
    RemoteQueryCommunity,
    sanitize_query, SelectResponsePayload,
)
from tribler.core.components.metadata_store.remote_query_community.settings import RemoteQueryCommunitySettings
from tribler.core.utilities.path_util import Path
from tribler.core.utilities.unicode import hexlify
from tribler.core.utilities.utilities import random_infohash


# pylint: disable=protected-access


def random_string():
    return ''.join(random.choices(string.ascii_uppercase + string.digits, k=100))


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


class BasicRemoteQueryCommunity(RemoteQueryCommunity):
    community_id = unhexlify('eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee')


class TestRemoteQueryCommunity(TriblerTestBase):
    """
    Unit tests for the base RemoteQueryCommunity which do not need a real Session.
    """

    def __init__(self, methodName='runTest'):
        random.seed(123)
        super().__init__(methodName)

    def setUp(self):
        random.seed(456)
        super().setUp()
        self.count = 0
        self.metadata_store_set = set()
        self.initialize(BasicRemoteQueryCommunity, 2)

    async def tearDown(self):
        for metadata_store in self.metadata_store_set:
            metadata_store.shutdown()
        await super().tearDown()

    def create_node(self, *args, **kwargs):
        metadata_store = MetadataStore(
            Path(self.temporary_directory()) / f"{self.count}.db",
            Path(self.temporary_directory()),
            default_eccrypto.generate_key("curve25519"),
            disable_sync=True,
        )
        self.metadata_store_set.add(metadata_store)
        kwargs['metadata_store'] = metadata_store
        kwargs['rqc_settings'] = RemoteQueryCommunitySettings()
        node = super().create_node(*args, **kwargs)
        self.count += 1
        return node

    def torrent_metadata(self, i):
        return self.nodes[i].overlay.mds.TorrentMetadata

    async def test_remote_select(self):
        """
        Test querying metadata entries from a remote machine
        """
        mds0 = self.nodes[0].overlay.mds
        mds1 = self.nodes[1].overlay.mds

        # Fill Node 0 DB with channels and torrents
        with db_session:
            for i in range(20):
                add_random_torrent(
                    mds0.TorrentMetadata,
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
            torrents0 = sorted(mds0.get_entries(**kwargs_dict), key=attrgetter('infohash'))
            torrents1 = sorted(mds1.get_entries(**kwargs_dict), key=attrgetter('infohash'))
            self.assertEqual(len(torrents0), len(torrents1))
            self.assertEqual(len(torrents0), 20)
            for t0, t1 in zip(torrents0, torrents1):
                assert t0.health.seeders == t1.health.seeders
                assert t0.health.leechers == t1.health.leechers
                assert t0.health.last_check == t1.health.last_check

        # Test getting empty response for a query
        kwargs_dict = {"txt_filter": "ubuntu*", "origin_id": 352127}
        callback = Mock()
        self.nodes[1].overlay.send_remote_select(self.nodes[0].my_peer, **kwargs_dict, processing_callback=callback)
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

    async def test_push_entry_update(self):
        """
        Test if sending back information on updated version of a metadata entry works
        """

    @pytest.mark.timeout(10)
    async def test_remote_select_torrents(self):
        """
        Test dropping packets that go over the response limit for a remote select.

        """
        peer = self.nodes[0].my_peer
        mds0 = self.nodes[0].overlay.mds
        mds1 = self.nodes[1].overlay.mds

        with db_session:
            torrent_infohash = random_infohash()
            mds0.TorrentMetadata(infohash=torrent_infohash, public_key=NULL_KEY, title='title1')

        callback_called = asyncio.Event()
        processing_results = []

        def callback(_, results):
            processing_results.extend(results)
            callback_called.set()

        self.nodes[1].overlay.send_remote_select(
            peer, metadata_type=[REGULAR_TORRENT], infohash=torrent_infohash, processing_callback=callback
        )

        await callback_called.wait()

        assert len(processing_results) == 1
        obj = processing_results[0].md_obj
        assert isinstance(obj, mds1.TorrentMetadata)
        assert obj.title == 'title1'
        assert obj.health.seeders == 0


    async def test_remote_select_packets_limit(self):
        """
        Test dropping packets that go over the response limit for a remote select.

        """
        mds0 = self.nodes[0].overlay.mds
        mds1 = self.nodes[1].overlay.mds

        with db_session:
            for _ in range(0, 100):
                md = add_random_torrent(mds0.TorrentMetadata, name=random_string())
                key = default_eccrypto.generate_key("curve25519")
                md.public_key = key.pub().key_to_bin()[10:]
                md.signature = md.serialized(key)[-64:]

        peer = self.nodes[0].my_peer
        kwargs_dict = {"metadata_type": [REGULAR_TORRENT]}
        self.nodes[1].overlay.send_remote_select(peer, **kwargs_dict)
        # There should be an outstanding request in the list
        self.assertTrue(self.nodes[1].overlay.request_cache._identifiers)  # pylint: disable=protected-access

        await self.deliver_messages(timeout=1.5)

        with db_session:
            received_torrents = list(mds1.TorrentMetadata.select())
            # We should receive less than 6 packets, so all the channels should not fit there.
            received_torrents_count = len(received_torrents)
            assert 40 <= received_torrents_count < 60

            # The list of outstanding requests should be empty
            self.assertFalse(self.nodes[1].overlay.request_cache._identifiers)  # pylint: disable=protected-access

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
            assert sanitize_query(req) == resp

    def test_sanitize_query_binary_fields(self):
        for field in ("infohash", "channel_pk"):
            field_in_b = b'0' * 20
            field_in_hex = hexlify(field_in_b)
            assert sanitize_query({field: field_in_hex})[field] == field_in_b

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

        mds0 = self.nodes[0].overlay.mds
        mds1 = self.nodes[1].overlay.mds

        value = urandom(10000)
        with db_session:
            add_random_torrent(mds1.TorrentMetadata, name=hexlify(value))

        kwargs_dict = {"metadata_type": [CHANNEL_THUMBNAIL]}
        callback = Mock()
        self.nodes[0].overlay.send_remote_select(self.nodes[1].my_peer, **kwargs_dict, processing_callback=callback)

        await self.deliver_messages(timeout=0.5)
        # Test optional response processing callback
        callback.assert_called()

        # All the matching torrent entries should have been sent to Node 1
        with db_session:
            torrents0 = mds0.get_entries(**kwargs_dict)
            torrents1 = mds1.get_entries(**kwargs_dict)
            self.assertEqual(len(torrents0), len(torrents1))

    async def test_drop_silent_peer(self):
        kwargs_dict = {"txt_filter": "ubuntu*"}

        basic_path = 'tribler.core.components.metadata_store.remote_query_community.remote_query_community'

        with self.overlay(1).request_cache.passthrough():
            # Stop peer 0 from responding
            with patch(basic_path + '.RemoteQueryCommunity._on_remote_select_basic'):
                self.nodes[1].overlay.network.remove_peer = Mock()
                self.nodes[1].overlay.send_remote_select(self.nodes[0].my_peer, **kwargs_dict)
                await sleep(0.0)
                # node 0 must have called remove_peer because of the timeout
                self.nodes[1].overlay.network.remove_peer.assert_called()

    async def test_dont_drop_silent_peer_on_empty_response(self):
        # Test that even in the case of an empty response packet, remove_peer is not called on timeout

        was_called = []

        async def mock_on_remote_select_response(*_, **__):
            was_called.append(True)
            return []

        kwargs_dict = {"txt_filter": "ubuntu*"}
        self.nodes[1].overlay.network.remove_peer = Mock()
        self.nodes[1].overlay.mds.process_compressed_mdblob_threaded = mock_on_remote_select_response
        self.nodes[1].overlay.send_remote_select(self.nodes[0].my_peer, **kwargs_dict)
        await self.deliver_messages()
        assert was_called  # Positive check to prevent always passing test
        self.nodes[1].overlay.network.remove_peer.assert_not_called()

    async def test_remote_select_force_eva(self):
        # Test requesting usage of EVA for sending multiple smaller entries
        with db_session:
            for _ in range(0, 10):
                add_random_torrent(self.nodes[1].overlay.mds.TorrentMetadata, name=hexlify(urandom(250)))

        kwargs_dict = {"metadata_type": [REGULAR_TORRENT]}

        self.nodes[1].overlay.eva.send_binary = Mock()
        self.nodes[0].overlay.send_remote_select(self.nodes[1].my_peer, **kwargs_dict, force_eva_response=True)

        await self.deliver_messages(timeout=0.5)

        self.nodes[1].overlay.eva.send_binary.assert_called_once()

    async def test_multiple_parallel_request(self):
        peer_a = self.nodes[0].my_peer
        a = self.nodes[0].overlay
        b = self.nodes[1].overlay

        # Peer A has two torrents "foo" and "bar"
        with db_session:
            add_random_torrent(a.mds.TorrentMetadata, name="foo")
            add_random_torrent(a.mds.TorrentMetadata, name="bar")

        # Peer B sends two parallel full-text search queries, only one of them should be processed
        callback1 = Mock()
        kwargs1 = {"txt_filter": "foo", "metadata_type": [REGULAR_TORRENT]}
        b.send_remote_select(peer_a, **kwargs1, processing_callback=callback1)

        callback2 = Mock()
        kwargs2 = {"txt_filter": "bar", "metadata_type": [REGULAR_TORRENT]}
        b.send_remote_select(peer_a, **kwargs2, processing_callback=callback2)

        original_get_entries = MetadataStore.get_entries

        # Add a delay to ensure that the first query is still being processed when the second one arrives
        # (the mds.get_entries() method is a synchronous one and is called from a worker thread)

        def slow_get_entries(self, *args, **kwargs):
            time.sleep(0.1)
            return original_get_entries(self, *args, **kwargs)

        with patch.object(a, 'logger') as logger, patch.object(MetadataStore, 'get_entries', slow_get_entries):
            await self.deliver_messages(timeout=0.5)

        torrents1 = list(b.mds.get_entries(**kwargs1))
        torrents2 = list(b.mds.get_entries(**kwargs2))

        # Both remote queries should return results to the peer B...
        assert callback1.called and callback2.called
        # ...but one of them should return an empty list, as the database query was not actually executed
        assert bool(torrents1) != bool(torrents2)

        # Check that on peer A there is exactly one warning about an ignored remote query
        warnings = [call.args[0] for call in logger.warning.call_args_list]
        assert len([msg for msg in warnings if msg.startswith('Ignore remote query')]) == 1
