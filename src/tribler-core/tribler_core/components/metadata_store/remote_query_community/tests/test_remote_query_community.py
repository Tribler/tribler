import random
from binascii import unhexlify
from datetime import datetime
from json import dumps
from operator import attrgetter
from os import urandom
from time import time
from unittest.mock import Mock, PropertyMock, patch

from ipv8.keyvault.crypto import default_eccrypto
from ipv8.test.base import TestBase

from pony.orm import db_session
from pony.orm.dbapiprovider import OperationalError

import pytest

from tribler_core.components.metadata_store.db.orm_bindings.channel_node import NEW
from tribler_core.components.metadata_store.db.serialization import CHANNEL_THUMBNAIL, CHANNEL_TORRENT, REGULAR_TORRENT
from tribler_core.components.metadata_store.db.store import MetadataStore
from tribler_core.components.metadata_store.remote_query_community.remote_query_community import RemoteQueryCommunity, \
    sanitize_query
from tribler_core.components.metadata_store.remote_query_community.settings import RemoteQueryCommunitySettings
from tribler_core.utilities.path_util import Path
from tribler_core.utilities.random_utils import random_infohash, random_string
from tribler_core.utilities.unicode import hexlify

# pylint: disable=protected-access


def add_random_torrent(metadata_cls, name="test", channel=None, seeders=None, leechers=None, last_check=None):
    d = {"infohash": random_infohash(), "title": name, "tags": "", "size": 1234, "status": NEW}
    if channel:
        d.update({"origin_id": channel.id_})
    torrent_metadata = metadata_cls.from_dict(d)
    torrent_metadata.sign()
    if seeders:
        torrent_metadata.health.seeders = seeders
    if leechers:
        torrent_metadata.health.leechers = leechers
    if last_check:
        torrent_metadata.health.last_check = last_check


class BasicRemoteQueryCommunity(RemoteQueryCommunity):
    community_id = unhexlify('eeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeeee')


class TestRemoteQueryCommunity(TestBase):
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
        self.torrent_template = {"title": "", "infohash": b"", "torrent_date": datetime(1970, 1, 1), "tags": "video"}

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

    def channel_metadata(self, i):
        return self.nodes[i].overlay.mds.ChannelMetadata

    def torrent_metadata(self, i):
        return self.nodes[i].overlay.mds.TorrentMetadata

    async def test_remote_select(self):
        """
        Test querying metadata entries from a remote machine
        """
        mds0 = self.nodes[0].overlay.mds
        mds1 = self.nodes[1].overlay.mds

        # We do not want the query back mechanism to interfere with this test
        self.nodes[1].overlay.rqc_settings.max_channel_query_back = 0

        # Fill Node 0 DB with channels and torrents
        with db_session:
            channel = mds0.ChannelMetadata.create_channel("ubuntu channel", "ubuntu")
            for i in range(20):
                add_random_torrent(
                    mds0.TorrentMetadata,
                    name=f"ubuntu {i}",
                    channel=channel,
                    seeders=2 * i,
                    leechers=i,
                    last_check=int(time()) + i,
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

    async def test_remote_select_query_back(self):
        """
        Test querying back preview contents for previously unknown channels.
        """
        num_channels = 5
        max_received_torrents_per_channel_query_back = 4

        mds0 = self.nodes[0].overlay.mds
        mds1 = self.nodes[1].overlay.mds

        with db_session:
            # Generate channels on Node 0
            for _ in range(0, num_channels):
                chan = mds0.ChannelMetadata.create_channel("channel", "")
                # Generate torrents in each channel
                for i in range(0, max_received_torrents_per_channel_query_back):
                    torrent = mds0.TorrentMetadata(origin_id=chan.id_, infohash=random_infohash())
                    torrent.health.seeders = i

        peer = self.nodes[0].my_peer
        kwargs_dict = {"metadata_type": [CHANNEL_TORRENT]}
        self.nodes[1].overlay.send_remote_select(peer, **kwargs_dict)

        await self.deliver_messages(timeout=0.5)

        with db_session:
            received_channels = list(mds1.ChannelMetadata.select(lambda g: g.title == "channel"))
            assert len(received_channels) == num_channels
            # For each unknown channel that we received, we should have queried the sender for 4 preview torrents.
            received_torrents = list(mds1.TorrentMetadata.select(lambda g: g.metadata_type == REGULAR_TORRENT))
            assert num_channels * max_received_torrents_per_channel_query_back == len(received_torrents)
            seeders = {t.health.seeders for t in received_torrents}
            assert seeders == set(range(max_received_torrents_per_channel_query_back))

    async def test_push_back_entry_update(self):
        """
        Test pushing back update for an entry.
        Scenario: both hosts 0 and 1 have metadata entries for the same channel,
        but host 1's version was created later (its timestamp is higher).
        When host 1 queries -> host 0 for channel info, host 0 sends it back.
        Upon receiving the response, host 1 sees that it has a newer version of the channel entry,
        so it pushes it back to host 0.
        """

        mds0 = self.nodes[0].overlay.mds
        mds1 = self.nodes[1].overlay.mds

        # Create the old and new versions of the test channel
        # We sign it with a different private key to prevent the special treatment
        # of personal channels during processing interfering with the test.
        fake_key = default_eccrypto.generate_key("curve25519")
        with db_session:
            chan = mds0.ChannelMetadata(infohash=random_infohash(), title="foo", sign_with=fake_key)
            # pylint: disable=protected-access
            chan_payload_old = chan._payload_class.from_signed_blob(chan.serialized())
            chan.timestamp = chan.timestamp + 1
            chan.sign(key=fake_key)
            # pylint: disable=protected-access
            chan_payload_updated = chan._payload_class.from_signed_blob(chan.serialized())
            chan.delete()

            # Add the older channel version to node 0
            mds0.ChannelMetadata.from_payload(chan_payload_old)

            # Add the updated channel version to node 1
            mds1.ChannelMetadata.from_payload(chan_payload_updated)

            # Just in case, assert the first node only got the older version for now
            assert mds0.ChannelMetadata.get(timestamp=chan_payload_old.timestamp)

        # Node 1 requests channel peers from node 0
        peer = self.nodes[0].my_peer
        kwargs_dict = {"metadata_type": [CHANNEL_TORRENT]}
        self.nodes[1].overlay.send_remote_select(peer, **kwargs_dict)
        await self.deliver_messages(timeout=0.5)

        with db_session:
            # Check that node0 now got the updated version
            assert mds0.ChannelMetadata.get(timestamp=chan_payload_updated.timestamp)

    async def test_push_entry_update(self):
        """
        Test if sending back information on updated version of a metadata entry works
        """

    async def test_remote_select_torrents(self):
        """
        Test dropping packets that go over the response limit for a remote select.

        """
        peer = self.nodes[0].my_peer
        mds0 = self.nodes[0].overlay.mds
        mds1 = self.nodes[1].overlay.mds

        with db_session:
            chan = mds0.ChannelMetadata.create_channel(random_string(100), "")
            torrent_infohash = random_infohash()
            torrent = mds0.TorrentMetadata(origin_id=chan.id_, infohash=torrent_infohash, title='title1')
            torrent.sign()

        processing_results = []

        def callback(request, results):  # pylint: disable=unused-argument
            processing_results.extend(results)

        self.nodes[1].overlay.send_remote_select(
            peer, metadata_type=[REGULAR_TORRENT], infohash=torrent_infohash, processing_callback=callback
        )
        await self.deliver_messages()

        assert len(processing_results) == 1
        obj = processing_results[0].md_obj
        assert isinstance(obj, mds1.TorrentMetadata)
        assert obj.title == 'title1'
        assert obj.health.seeders == 0

        with db_session:
            torrent = mds0.TorrentMetadata.get(infohash=torrent_infohash)
            torrent.timestamp += 1
            torrent.title = 'title2'
            torrent.sign()

        processing_results = []
        self.nodes[1].overlay.send_remote_select(
            peer, metadata_type=[REGULAR_TORRENT], infohash=torrent_infohash, processing_callback=callback
        )
        await self.deliver_messages()

        assert len(processing_results) == 1
        obj = processing_results[0].md_obj
        assert isinstance(obj, mds1.TorrentMetadata)
        assert obj.health.seeders == 0

    async def test_remote_select_packets_limit(self):
        """
        Test dropping packets that go over the response limit for a remote select.

        """
        mds0 = self.nodes[0].overlay.mds
        mds1 = self.nodes[1].overlay.mds

        # We do not want the query back mechanism to interfere with this test
        self.nodes[1].overlay.rqc_settings.max_channel_query_back = 0

        with db_session:
            for _ in range(0, 100):
                mds0.ChannelMetadata.create_channel(random_string(100), "")

        peer = self.nodes[0].my_peer
        kwargs_dict = {"metadata_type": [CHANNEL_TORRENT]}
        self.nodes[1].overlay.send_remote_select(peer, **kwargs_dict)
        # There should be an outstanding request in the list
        self.assertTrue(self.nodes[1].overlay.request_cache._identifiers)  # pylint: disable=protected-access

        await self.deliver_messages(timeout=1.5)

        with db_session:
            received_channels = list(mds1.ChannelMetadata.select())
            # We should receive less that 6 packets, so all the channels should not fit there.
            received_channels_count = len(received_channels)
            assert 40 < received_channels_count < 60

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
            channel = self.channel_metadata(0).create_channel("a channel", "")
            add_random_torrent(self.torrent_metadata(0), name="a torrent", channel=channel)

        results = await self.overlay(0).process_rpc_query(dumps({}))
        self.assertEqual(2, len(results))

        channel_md, torrent_md = results if isinstance(results[0], self.channel_metadata(0)) else results[::-1]
        self.assertEqual("a channel", channel_md.title)
        self.assertEqual("a torrent", torrent_md.title)

    async def test_process_rpc_query_match_one(self):
        """
        Check if a correct query with one match in our database returns one result.
        """
        with db_session:
            self.channel_metadata(0).create_channel("a channel", "")

        results = await self.overlay(0).process_rpc_query(dumps({}))
        self.assertEqual(1, len(results))

        (channel_md,) = results
        self.assertEqual("a channel", channel_md.title)

    async def test_process_rpc_query_match_none(self):
        """
        Check if a correct query with no match in our database returns no result.
        """
        results = await self.overlay(0).process_rpc_query(dumps({}))
        self.assertEqual(0, len(results))

    async def test_process_rpc_query_match_empty_json(self):
        """
        Check if processing an empty request causes a ValueError (JSONDecodeError) to be raised.
        """
        with self.assertRaises(ValueError):
            await self.overlay(0).process_rpc_query(b'')

    async def test_process_rpc_query_match_illegal_json(self):
        """
        Check if processing a request with illegal JSON causes a UnicodeDecodeError to be raised.
        """
        with self.assertRaises(UnicodeDecodeError):
            await self.overlay(0).process_rpc_query(b'{"akey":\x80}')

    async def test_process_rpc_query_match_invalid_json(self):
        """
        Check if processing a request with invalid JSON causes a ValueError to be raised.
        """
        with db_session:
            self.channel_metadata(0).create_channel("a channel", "")
        query = b'{"id_":' + b'\x31' * 200 + b'}'
        with self.assertRaises(ValueError):
            await self.overlay(0).process_rpc_query(query)

    async def test_process_rpc_query_match_invalid_key(self):
        """
        Check if processing a request with invalid flags causes a UnicodeDecodeError to be raised.
        """
        with self.assertRaises(TypeError):
            await self.overlay(0).process_rpc_query(b'{"bla":":("}')

    async def test_process_rpc_query_no_column(self):
        """
        Check if processing a request with no database columns causes an OperationalError.
        """
        with self.assertRaises(OperationalError):
            await self.overlay(0).process_rpc_query(b'{"txt_filter":{"key":"bla"}}')

    async def test_remote_query_big_response(self):

        mds0 = self.nodes[0].overlay.mds
        mds1 = self.nodes[1].overlay.mds

        value = urandom(20000)
        with db_session:
            mds1.ChannelThumbnail(binary_data=value)

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

    @pytest.mark.timeout(15)
    async def test_remote_select_query_back_thumbs_and_descriptions(self):
        """
        Test querying back preview thumbnail and description for previously unknown and updated channels.
        """
        mds0 = self.nodes[0].overlay.mds
        mds1 = self.nodes[1].overlay.mds

        with db_session:
            # Generate channels on Node 0
            chan = mds0.ChannelMetadata.create_channel("channel", "")
            mds0.ChannelThumbnail(
                public_key=chan.public_key,
                origin_id=chan.id_,
                binary_data=urandom(2000),
                data_type="image/png",
                status=NEW,
            )

            mds0.ChannelDescription(
                public_key=chan.public_key, origin_id=chan.id_, json_text='{"description_text": "foobar"}', status=NEW
            )
            chan.commit_all_channels()
            chan_v = chan.timestamp

        peer = self.nodes[0].my_peer
        kwargs_dict = {"metadata_type": [CHANNEL_TORRENT]}
        self.nodes[1].overlay.send_remote_select(peer, **kwargs_dict)

        await self.deliver_messages(timeout=0.5)

        with db_session:
            assert mds1.ChannelMetadata.get(lambda g: g.title == "channel")
            assert mds1.ChannelThumbnail.get()
            assert mds1.ChannelDescription.get()

        # Now test querying for updated version of description/thumbnail
        with db_session:
            thumb = mds0.ChannelThumbnail.get()
            new_pic_bytes = urandom(2500)
            thumb.update_properties({"binary_data": new_pic_bytes})
            descr = mds0.ChannelDescription.get()
            descr.update_properties({"json_text": '{"description_text": "yummy"}'})

            chan = mds0.ChannelMetadata.get()
            chan.commit_all_channels()
            chan_v2 = chan.timestamp
            assert chan_v2 > chan_v

        self.nodes[1].overlay.send_remote_select(peer, **kwargs_dict)

        await self.deliver_messages(timeout=1)

        with db_session:
            assert mds1.ChannelMetadata.get(lambda g: g.title == "channel")
            assert mds1.ChannelThumbnail.get().binary_data == new_pic_bytes
            assert mds1.ChannelDescription.get().json_text == '{"description_text": "yummy"}'

        # Test querying for missing dependencies (e.g. thumbnails and descriptions lost due to transfer errors)
        with db_session:
            mds1.ChannelThumbnail.get().delete()
            mds1.ChannelDescription.get().delete()
        self.nodes[1].overlay.send_remote_select(peer, **kwargs_dict)

        await self.deliver_messages(timeout=1)

        with db_session:
            mds1.ChannelThumbnail.get()
            mds1.ChannelDescription.get()

        # Test that we're only going to query for updated objects and skip old ones
        with db_session:
            chan = mds0.ChannelMetadata.get()
            mds0.TorrentMetadata(public_key=chan.public_key, origin_id=chan.id_, infohash=random_infohash(), status=NEW)

            chan.commit_all_channels()
            chan_v3 = chan.timestamp
            assert chan_v3 > chan_v2

        self.nodes[0].overlay.eva_send_binary = Mock()

        self.nodes[1].overlay.send_remote_select(peer, **kwargs_dict)
        await self.deliver_messages(timeout=1)

        # Big transfer should not have been called, because we only queried for updated version of the thumbnail
        self.nodes[0].overlay.eva_send_binary.assert_not_called()

        with db_session:
            assert mds1.ChannelMetadata.get(lambda g: g.title == "channel").timestamp == chan_v3

    @pytest.mark.timeout(5)
    async def test_drop_silent_peer(self):

        # We do not want the query back mechanism to interfere with this test
        self.nodes[1].overlay.rqc_settings.max_channel_query_back = 0

        kwargs_dict = {"txt_filter": "ubuntu*"}

        basic_path = 'tribler_core.components.metadata_store.remote_query_community.remote_query_community'

        with patch(basic_path + '.SelectRequest.timeout_delay', new_callable=PropertyMock) as delay_mock:
            # Change query timeout to a really low value
            delay_mock.return_value = 0.3

            # Stop peer 0 from responding
            with patch(basic_path + '.RemoteQueryCommunity._on_remote_select_basic'):
                self.nodes[1].overlay.network.remove_peer = Mock()
                self.nodes[1].overlay.send_remote_select(self.nodes[0].my_peer, **kwargs_dict)
                await self.deliver_messages(timeout=1)
                # node 0 must have called remove_peer because of the timeout
                self.nodes[1].overlay.network.remove_peer.assert_called()

            # Now test that even in the case of an empty response packet, remove_peer is not called on timeout
            self.nodes[1].overlay.network.remove_peer = Mock()
            self.nodes[1].overlay.send_remote_select(self.nodes[0].my_peer, **kwargs_dict)
            await self.deliver_messages(timeout=1)
            self.nodes[1].overlay.network.remove_peer.assert_not_called()

    async def test_remote_select_force_eva(self):
        # Test requesting usage of EVA for sending multiple smaller entries
        with db_session:
            for _ in range(0, 10):
                self.nodes[1].overlay.mds.ChannelThumbnail(binary_data=urandom(500))

        kwargs_dict = {"metadata_type": [CHANNEL_THUMBNAIL]}

        self.nodes[1].overlay.eva_send_binary = Mock()
        self.nodes[0].overlay.send_remote_select(self.nodes[1].my_peer, **kwargs_dict, force_eva_response=True)

        await self.deliver_messages(timeout=0.5)

        self.nodes[1].overlay.eva_send_binary.assert_called_once()
