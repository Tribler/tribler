import time
from collections.abc import Mapping
from dataclasses import asdict, dataclass, fields
from typing import Callable
from unittest.mock import AsyncMock, Mock

import pytest
from ipv8.keyvault.crypto import default_eccrypto
from ipv8.peer import Peer
from pony.orm import db_session

from tribler.core.components.gigachannel.community.gigachannel_community import (
    ChannelsPeersMapping,
    GigaChannelCommunity,
    NoChannelSourcesException,
    happy_eyeballs_delay
)
from tribler.core.components.gigachannel.community.settings import ChantSettings
from tribler.core.components.ipv8.adapters_tests import TriblerTestBase
from tribler.core.components.metadata_store.db.store import MetadataStore
from tribler.core.components.metadata_store.remote_query_community.remote_query_community import EvaSelectRequest, \
    SelectRequest, RemoteSelectPayload, RemoteSelectPayloadEva, SelectResponsePayload
from tribler.core.components.metadata_store.remote_query_community.settings import RemoteQueryCommunitySettings
from tribler.core.components.metadata_store.utils import RequestTimeoutException
from tribler.core.utilities.notifier import Notifier
from tribler.core.utilities.path_util import Path
from tribler.core.utilities.utilities import random_infohash

# pylint:disable=protected-access

EMPTY_BLOB = b""
U_CHANNEL = "ubuntu channel"
U_TORRENT = "ubuntu torrent"
CHANNEL_ID = 123
BASE_PATH = 'tribler.core.components.metadata_store.remote_query_community.remote_query_community'
ID1, ID2, ID3 = range(3)


@dataclass
class ChannelKey(Mapping):
    channel_pk: bytes
    origin_id: int

    # The following methods allow for use as a Mapping (i.e., the "**key"-syntax)
    def __iter__(self):
        return iter(asdict(self))

    def __getitem__(self, item):
        return getattr(self, item)

    def __len__(self):
        return len(fields(self))


class TestGigaChannelUnits(TriblerTestBase):
    overlay: Callable[[int], GigaChannelCommunity]

    def setUp(self):
        super().setUp()
        self.count = 0
        self.metadata_store_set = set()
        self.initialize(GigaChannelCommunity, 3)

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
        kwargs['settings'] = ChantSettings()
        kwargs['rqc_settings'] = RemoteQueryCommunitySettings()
        node = super().create_node(*args, **kwargs)

        node.overlay.discovery_booster.finish()
        notifier = Notifier(loop=self.loop)
        notifier.notify = Mock()
        node.overlay.notifier = notifier

        self.count += 1
        return node

    def channel_metadata(self, i):
        return self.overlay(i).mds.ChannelMetadata

    def torrent_metadata(self, i):
        return self.overlay(i).mds.TorrentMetadata

    def notifier(self, i):
        return self.overlay(i).notifier

    def channel_pk(self, i):
        return self.key_bin(i)[10:]

    def generate_torrents(self, overlay) -> ChannelKey:
        private_key = default_eccrypto.generate_key("curve25519")
        channel_key = ChannelKey(private_key.pub().key_to_bin()[10:], CHANNEL_ID)
        with db_session:
            for m in range(0, 50):
                overlay.mds.TorrentMetadata(
                    title=f"bla-{m}", origin_id=channel_key.origin_id, infohash=random_infohash(), sign_with=private_key
                )
        return channel_key

    async def test_gigachannel_search(self):
        """
        Test searching several nodes for metadata entries based on title text
        """

        # We do not want the query back mechanism and introduction callback to interfere with this test
        for node in self.nodes:
            node.overlay.rqc_settings.max_channel_query_back = 0

        with db_session:
            # Add test metadata to node ID1
            self.channel_metadata(ID1).create_channel(U_CHANNEL, "")
            self.channel_metadata(ID1).create_channel("debian channel", "")
            # Add test metadata to node ID2
            self.torrent_metadata(ID2)(title=U_TORRENT, infohash=random_infohash())
            self.torrent_metadata(ID2)(title="debian torrent", infohash=random_infohash())

        self.overlay(ID3).send_search_request(**{"txt_filter": "ubuntu*"})

        await self.deliver_messages()

        # Check that the notifier callback was called on both entries
        titles = sorted(call.args[1]["results"][0]["name"] for call in self.notifier(ID3).notify.call_args_list)
        assert titles == [U_CHANNEL, U_TORRENT]

        with db_session:
            assert self.overlay(ID3).mds.ChannelNode.select().count() == 2
            assert self.overlay(ID3).mds.ChannelNode.select(lambda g: g.title in (U_CHANNEL, U_TORRENT)).count() == 2

    async def test_query_on_introduction(self):
        """
        Test querying a peer that was just introduced to us.
        """
        with self.assertReceivedBy(ID1, [SelectResponsePayload], message_filter=[SelectResponsePayload]):
            self.overlay(ID2).send_introduction_request(self.peer(ID1))
            await self.deliver_messages()
        self.assertIn(self.mid(ID1), self.overlay(ID2).queried_peers)

        # Make sure the same peer will not be queried twice in case the walker returns to it
        with self.assertReceivedBy(ID1, [], message_filter=[SelectResponsePayload]):
            self.overlay(ID2).send_introduction_request(self.peer(ID1))
            await self.deliver_messages()

        # Test clearing queried peers set when it outgrows its capacity
        self.overlay(ID2).settings.queried_peers_limit = 2
        with self.assertReceivedBy(ID3, [SelectResponsePayload], message_filter=[SelectResponsePayload]):
            self.overlay(ID2).send_introduction_request(self.peer(ID3))
            await self.deliver_messages()
        self.assertEqual(len(self.overlay(ID2).queried_peers), 2)

        self.add_node_to_experiment(self.create_node())
        with self.assertReceivedBy(3, [SelectResponsePayload], message_filter=[SelectResponsePayload]):
            self.overlay(ID2).send_introduction_request(self.peer(3))
            await self.deliver_messages()
        # The set has been cleared, so the number of queried peers must be dropped back to 1
        self.assertEqual(len(self.overlay(ID2).queried_peers), 1)

        # Ensure that we're not going to query ourselves
        with self.assertReceivedBy(ID1, [], message_filter=[SelectResponsePayload]):
            self.overlay(ID2).send_introduction_request(self.peer(ID2))
        self.assertEqual(len(self.overlay(ID2).queried_peers), 1)

    async def test_remote_select_subscribed_channels(self):
        """
        Test querying remote peers for subscribed channels and updating local votes accordingly.
        """

        # We do not want the query back mechanism to interfere with this test
        self.overlay(ID2).rqc_settings.max_channel_query_back = 0

        num_channels = 5

        with db_session:
            # Create one channel with zero contents, to check that only non-empty channels are served
            self.channel_metadata(ID1).create_channel("channel sub", "")
            # Create one channel that has not yet been processed (with local_version<timestamp)
            incomplete_chan = self.channel_metadata(ID1).create_channel("channel sub", "")
            incomplete_chan.num_entries = 10
            incomplete_chan.sign()
            for _ in range(0, num_channels):
                chan = self.channel_metadata(ID1).create_channel("channel sub", "")
                chan.local_version = chan.timestamp
                chan.num_entries = 10
                chan.sign()
            for _ in range(0, num_channels):
                channel_uns = self.channel_metadata(ID1).create_channel("channel unsub", "")
                channel_uns.subscribed = False

        await self.introduce_nodes()
        await self.deliver_messages()

        # Check that the notifier callback is called on new channel entries
        self.notifier(ID2).notify.assert_called()
        assert "results" in self.notifier(ID2).notify.call_args.args[1]

        with db_session:
            received_channels = self.channel_metadata(ID2).select(lambda g: g.title == "channel sub")
            self.assertEqual(num_channels, received_channels.count())

            # Only subscribed channels should have been transported
            received_channels_all = self.channel_metadata(ID2).select()
            self.assertEqual(num_channels, received_channels_all.count())

            # Make sure the subscribed channels transport counted as voting
            self.assertEqual(self.overlay(ID2).mds.ChannelPeer.select().first().public_key, self.channel_pk(ID1))
            for chan in self.channel_metadata(ID2).select():
                self.assertTrue(chan.votes > 0.0)

    def test_channels_peers_mapping_drop_excess_peers(self):
        """
        Test dropping old excess peers from a channel to peers mapping
        """
        mapping = ChannelsPeersMapping()
        key = ChannelKey(self.channel_pk(ID1), CHANNEL_ID)

        num_excess_peers = 20
        t = time.time() - 1000
        first_peer_timestamp = t
        for k in range(0, mapping.max_peers_per_channel + num_excess_peers):
            peer = Peer(default_eccrypto.generate_key("very-low"), ("1.2.3.4", 5))
            peer.last_response = t
            t += 1.0
            mapping.add(peer, *key.values())
            if k == 0:
                first_peer_timestamp = peer.last_response

        chan_peers_3 = mapping.get_last_seen_peers_for_channel(*key.values(), limit=3)
        assert len(chan_peers_3) == 3

        chan_peers = mapping.get_last_seen_peers_for_channel(*key.values())
        assert len(chan_peers) == mapping.max_peers_per_channel

        assert chan_peers_3 == chan_peers[0:3]
        assert chan_peers == sorted(chan_peers, key=lambda x: x.last_response, reverse=True)

        # Make sure only the older peers are dropped as excess
        for p in chan_peers:
            assert p.last_response > first_peer_timestamp

        # Test removing a peer directly, e.g. as a result of a query timeout
        peer = Peer(default_eccrypto.generate_key("very-low"), ("1.2.3.4", 5))
        mapping.add(peer, *key.values())
        mapping.remove_peer(peer)
        for p in chan_peers:
            mapping.remove_peer(p)

        assert mapping.get_last_seen_peers_for_channel(*key.values()) == []

        # Make sure the stuff is cleaned up
        assert len(mapping._peers_channels) == 0
        assert len(mapping._channels_dict) == 0

    def test_get_known_subscribed_peers_for_node(self):
        key = default_eccrypto.generate_key("curve25519")
        with db_session:
            channel = self.channel_metadata(ID1)(origin_id=0, infohash=random_infohash(), sign_with=key)
            folder1 = self.overlay(ID1).mds.CollectionNode(origin_id=channel.id_, sign_with=key)
            folder2 = self.overlay(ID1).mds.CollectionNode(origin_id=folder1.id_, sign_with=key)

            orphan = self.overlay(ID1).mds.CollectionNode(origin_id=123123, sign_with=key)

        self.overlay(ID1).channels_peers.add(self.peer(ID2), channel.public_key, channel.id_)
        expected = [self.peer(ID2)]
        assert expected == self.overlay(ID1).get_known_subscribed_peers_for_node(channel.public_key, channel.id_)
        assert expected == self.overlay(ID1).get_known_subscribed_peers_for_node(folder1.public_key, folder1.id_)
        assert expected == self.overlay(ID1).get_known_subscribed_peers_for_node(folder2.public_key, folder2.id_)
        assert [] == self.overlay(ID1).get_known_subscribed_peers_for_node(orphan.public_key, orphan.id_)

    async def test_remote_search_mapped_peers(self):
        """
        Test using mapped peers for channel queries.
        """
        key = ChannelKey(self.channel_pk(ID1), CHANNEL_ID)
        self.network(ID3).remove_peer(self.peer(ID1))
        self.network(ID3).remove_peer(self.peer(ID2))
        self.overlay(ID3).channels_peers.add(self.peer(ID2), *key.values())

        # The only source for peers is channels peers map
        # The peer must have queried its known channel peer
        with self.assertReceivedBy(ID2, [RemoteSelectPayload, SelectResponsePayload]):
            self.overlay(ID3).send_search_request(**key)
            await self.deliver_messages()

    async def test_drop_silent_peer(self):
        # We do not want the query back mechanism to interfere with this test
        self.overlay(ID2).rqc_settings.max_channel_query_back = 0
        self.overlay(ID2).channels_peers.add(self.peer(ID1), self.channel_pk(ID1), CHANNEL_ID)

        seen_peers = self.overlay(ID2).channels_peers.get_last_seen_peers_for_channel(self.channel_pk(ID1), CHANNEL_ID)
        assert [self.peer(ID1)] == seen_peers

        with self.overlay(ID2).request_cache.passthrough(SelectRequest):
            self.overlay(ID2).send_remote_select(self.peer(ID1), txt_filter="ubuntu*")
            await self.deliver_messages()

        # the `remove_peer` function must have been called because of the timeout
        seen_peers = self.overlay(ID2).channels_peers.get_last_seen_peers_for_channel(self.channel_pk(ID1), CHANNEL_ID)
        assert [] == seen_peers

    async def test_drop_silent_peer_empty_response_packet(self):
        # We do not want the query back mechanism to interfere with this test
        self.overlay(ID2).rqc_settings.max_channel_query_back = 0
        self.overlay(ID2).channels_peers.add(self.peer(ID1), self.channel_pk(ID1), CHANNEL_ID)

        seen_peers = self.overlay(ID2).channels_peers.get_last_seen_peers_for_channel(self.channel_pk(ID1), CHANNEL_ID)
        assert [self.peer(ID1)] == seen_peers

        # Now test that even in the case of an empty response packet, remove_peer is not called on timeout
        self.overlay(ID2).send_remote_select(self.peer(ID1), txt_filter="ubuntu*")
        await self.deliver_messages()

        # the `remove_peer` function must not have been called because of the timeout
        seen_peers = self.overlay(ID2).channels_peers.get_last_seen_peers_for_channel(self.channel_pk(ID1), CHANNEL_ID)
        assert [self.peer(ID1)] == seen_peers

    async def test_remote_select_channel_contents(self):
        """
        Test awaiting for response from remote peer
        """
        key = self.generate_torrents(self.overlay(ID2))
        with db_session:
            self.overlay(ID1).channels_peers.add(self.peer(ID2), *key.values())
            generated = [p.to_simple_dict() for p in self.overlay(ID2).mds.get_entries(**key)]

        results = await self.overlay(ID1).remote_select_channel_contents(**key)

        assert results == generated
        assert len(results) == 50

    async def test_remote_select_channel_contents_empty(self):
        """
        Test awaiting for response from remote peer and getting empty results
        """
        key = ChannelKey(self.channel_pk(ID3), CHANNEL_ID)
        with db_session:
            self.overlay(ID1).channels_peers.add(self.peer(ID2), *key.values())

        results = await self.overlay(ID1).remote_select_channel_contents(**key)

        assert [] == results

    async def test_remote_select_channel_timeout(self):
        key = self.generate_torrents(self.overlay(ID2))
        with db_session:
            self.overlay(ID1).channels_peers.add(self.peer(ID2), *key.values())
        self.overlay(ID2).endpoint.close()

        with pytest.raises(RequestTimeoutException):
            with self.overlay(ID1).request_cache.passthrough(EvaSelectRequest):  # Immediately timeout the cache
                await self.overlay(ID1).remote_select_channel_contents(**key)

    async def test_remote_select_channel_no_peers(self):
        key = self.generate_torrents(self.overlay(ID2))

        with pytest.raises(NoChannelSourcesException):
            await self.overlay(ID1).remote_select_channel_contents(**key)

    async def test_remote_select_channel_contents_happy_eyeballs(self):
        """
        Test trying to connect to the first server, then timing out and falling back to the second one
        """
        key = self.generate_torrents(self.overlay(ID3))
        with db_session:
            self.overlay(ID1).channels_peers.add(self.peer(ID2), *key.values())
            self.overlay(ID1).channels_peers.add(self.peer(ID3), *key.values())

        # Neither responds early, so each should act as each others fallback.
        # Neither responds at all actually, so the remote select will time out.
        self.overlay(ID2)._on_remote_select_basic = AsyncMock()
        self.overlay(ID3)._on_remote_select_basic = AsyncMock()

        # Check that ID2 received a call
        with self.assertReceivedBy(ID2, [RemoteSelectPayloadEva]):
            # Check that ID3 received a call
            with self.assertReceivedBy(ID3, [RemoteSelectPayloadEva]):
                # Make sure that happy_eyeballs_delay finishes.
                # Both ID2 and ID3 should then have received a request (asserted by assertReceivedBy)
                with self.overlay(ID1).request_cache.passthrough(timeout=happy_eyeballs_delay + 0.05):
                    with self.assertRaises(RequestTimeoutException):
                        await self.overlay(ID1).remote_select_channel_contents(**key)
