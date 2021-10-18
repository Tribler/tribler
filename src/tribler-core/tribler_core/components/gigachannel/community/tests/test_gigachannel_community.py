import time
from datetime import datetime
from unittest import mock
from unittest.mock import AsyncMock, Mock, PropertyMock, patch

from ipv8.keyvault.crypto import default_eccrypto
from ipv8.peer import Peer
from ipv8.test.base import TestBase

from pony.orm import db_session

import pytest

from tribler_core.components.gigachannel.community.gigachannel_community import (
    ChannelsPeersMapping,
    GigaChannelCommunity,
    NoChannelSourcesException,
)
from tribler_core.components.gigachannel.community.settings import ChantSettings
from tribler_core.components.metadata_store.db.store import MetadataStore
from tribler_core.components.metadata_store.remote_query_community.settings import RemoteQueryCommunitySettings
from tribler_core.components.metadata_store.utils import RequestTimeoutException
from tribler_core.notifier import Notifier
from tribler_core.utilities.path_util import Path
from tribler_core.utilities.random_utils import random_infohash

EMPTY_BLOB = b""

# pylint:disable=protected-access

BASE_PATH = 'tribler_core.components.metadata_store.remote_query_community.remote_query_community'


class TestGigaChannelUnits(TestBase):
    def setUp(self):
        super().setUp()
        self.count = 0
        self.metadata_store_set = set()
        self.initialize(GigaChannelCommunity, 3)
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
        kwargs['settings'] = ChantSettings()
        kwargs['rqc_settings'] = RemoteQueryCommunitySettings()
        with mock.patch('tribler_core.components.gigachannel.community.gigachannel_community.DiscoveryBooster'):
            node = super().create_node(*args, **kwargs)
        self.count += 1
        return node

    def channel_metadata(self, i):
        return self.nodes[i].overlay.mds.ChannelMetadata

    def torrent_metadata(self, i):
        return self.nodes[i].overlay.mds.TorrentMetadata

    def generate_torrents(self, overlay):
        key = default_eccrypto.generate_key("curve25519")
        channel_pk = key.pub().key_to_bin()[10:]
        channel_id = 123
        kwargs = {"channel_pk": channel_pk, "origin_id": channel_id}
        with db_session:
            for m in range(0, 50):
                overlay.mds.TorrentMetadata(
                    title=f"bla-{m}", origin_id=channel_id, infohash=random_infohash(), sign_with=key
                )
        return kwargs

    def client_server_request_setup(self):
        client = self.overlay(0)
        server = self.overlay(2)
        kwargs = self.generate_torrents(server)
        client.get_known_subscribed_peers_for_node = lambda *_: [server.my_peer]
        return client, server, kwargs

    def double_client_server_request_setup(self):
        client = self.overlay(0)
        server1 = self.overlay(1)
        server2 = self.overlay(2)
        kwargs_server2 = self.generate_torrents(server2)
        client.get_known_subscribed_peers_for_node = lambda *_: [server1.my_peer, server2.my_peer]
        return client, server1, server2, kwargs_server2

    async def test_gigachannel_search(self):
        """
        Test searching several nodes for metadata entries based on title text
        """

        # We do not want the query back mechanism and introduction callback to interfere with this test
        for node in self.nodes:
            node.overlay.rqc_settings.max_channel_query_back = 0

        await self.introduce_nodes()

        U_CHANNEL = "ubuntu channel"
        U_TORRENT = "ubuntu torrent"

        # Add test metadata to node 0
        with db_session:
            self.nodes[0].overlay.mds.ChannelMetadata.create_channel(U_CHANNEL, "")
            self.nodes[0].overlay.mds.ChannelMetadata.create_channel("debian channel", "")

        # Add test metadata to node 1
        with db_session:
            self.nodes[1].overlay.mds.TorrentMetadata(title=U_TORRENT, infohash=random_infohash())
            self.nodes[1].overlay.mds.TorrentMetadata(title="debian torrent", infohash=random_infohash())

        notification_calls = []

        def mock_notify(_, args):
            notification_calls.append(args)

        self.nodes[2].overlay.notifier = Notifier()
        self.nodes[2].overlay.notifier.notify = lambda sub, args: mock_notify(self.nodes[2].overlay, args)

        self.nodes[2].overlay.send_search_request(**{"txt_filter": "ubuntu*"})

        await self.deliver_messages(timeout=0.5)

        with db_session:
            assert self.nodes[2].overlay.mds.ChannelNode.select().count() == 2
            assert (
                self.nodes[2].overlay.mds.ChannelNode.select(lambda g: g.title in (U_CHANNEL, U_TORRENT)).count() == 2
            )

        # Check that the notifier callback was called on both entries
        assert [U_CHANNEL, U_TORRENT] == sorted([c["results"][0]["name"] for c in notification_calls])

    def test_query_on_introduction(self):
        """
        Test querying a peer that was just introduced to us.
        """

        send_ok = []

        def mock_send(_):
            send_ok.append(1)

        self.nodes[1].overlay.send_remote_select_subscribed_channels = mock_send
        peer = self.nodes[0].my_peer
        payload = Mock()
        self.nodes[1].overlay.introduction_response_callback(peer, None, payload)
        self.assertIn(peer.mid, self.nodes[1].overlay.queried_peers)
        self.assertTrue(send_ok)

        # Make sure the same peer will not be queried twice in case the walker returns to it
        self.nodes[1].overlay.introduction_response_callback(peer, None, payload)
        self.assertEqual(len(send_ok), 1)

        # Test clearing queried peers set when it outgrows its capacity
        self.nodes[1].overlay.settings.queried_peers_limit = 2
        self.nodes[1].overlay.introduction_response_callback(Peer(default_eccrypto.generate_key("low")), None, payload)
        self.assertEqual(len(self.nodes[1].overlay.queried_peers), 2)

        self.nodes[1].overlay.introduction_response_callback(Peer(default_eccrypto.generate_key("low")), None, payload)
        # The set has been cleared, so the number of queried peers must be dropped back to 1
        self.assertEqual(len(self.nodes[1].overlay.queried_peers), 1)

        # Ensure that we're not going to query ourselves
        self.nodes[1].overlay.introduction_response_callback(self.nodes[1].overlay.my_peer, None, payload)
        self.assertEqual(len(send_ok), 3)

    async def test_remote_select_subscribed_channels(self):
        """
        Test querying remote peers for subscribed channels and updating local votes accordingly.
        """

        # We do not want the query back mechanism to interfere with this test
        self.nodes[1].overlay.rqc_settings.max_channel_query_back = 0

        num_channels = 5

        with db_session:
            # Create one channel with zero contents, to check that only non-empty channels are served
            self.nodes[0].overlay.mds.ChannelMetadata.create_channel("channel sub", "")
            # Create one channel that has not yet been processed (with local_version<timestamp)
            incomplete_chan = self.nodes[0].overlay.mds.ChannelMetadata.create_channel("channel sub", "")
            incomplete_chan.num_entries = 10
            incomplete_chan.sign()
            for _ in range(0, num_channels):
                chan = self.nodes[0].overlay.mds.ChannelMetadata.create_channel("channel sub", "")
                chan.local_version = chan.timestamp
                chan.num_entries = 10
                chan.sign()
            for _ in range(0, num_channels):
                channel_uns = self.nodes[0].overlay.mds.ChannelMetadata.create_channel("channel unsub", "")
                channel_uns.subscribed = False

        def mock_notify(overlay, args):
            overlay.notified_results = True
            self.assertTrue("results" in args)

        self.nodes[1].overlay.notifier = Notifier()
        self.nodes[1].overlay.notifier.notify = lambda sub, args: mock_notify(self.nodes[1].overlay, args)

        peer = self.nodes[0].my_peer
        await self.introduce_nodes()

        await self.deliver_messages(timeout=0.5)

        with db_session:
            received_channels = self.nodes[1].overlay.mds.ChannelMetadata.select(lambda g: g.title == "channel sub")
            self.assertEqual(num_channels, received_channels.count())

            # Only subscribed channels should have been transported
            received_channels_all = self.nodes[1].overlay.mds.ChannelMetadata.select()
            self.assertEqual(num_channels, received_channels_all.count())

            # Make sure the subscribed channels transport counted as voting
            self.assertEqual(
                self.nodes[1].overlay.mds.ChannelPeer.select().first().public_key, peer.public_key.key_to_bin()[10:]
            )
            for chan in self.nodes[1].overlay.mds.ChannelMetadata.select():
                self.assertTrue(chan.votes > 0.0)

        # Check that the notifier callback is called on new channel entries
        self.assertTrue(self.nodes[1].overlay.notified_results)

    def test_channels_peers_mapping_drop_excess_peers(self):
        """
        Test dropping old excess peers from a channel to peers mapping
        """
        mapping = ChannelsPeersMapping()
        chan_pk = Mock()
        chan_id = 123

        num_excess_peers = 20
        first_peer_timestamp = None
        for k in range(0, mapping.max_peers_per_channel + num_excess_peers):
            peer = Peer(default_eccrypto.generate_key("very-low"), ("1.2.3.4", 5))
            peer.last_response = time.time()
            mapping.add(peer, chan_pk, chan_id)
            if k == 0:
                first_peer_timestamp = peer.last_response

        chan_peers_3 = mapping.get_last_seen_peers_for_channel(chan_pk, chan_id, 3)
        assert len(chan_peers_3) == 3

        chan_peers = mapping.get_last_seen_peers_for_channel(chan_pk, chan_id)
        assert len(chan_peers) == mapping.max_peers_per_channel

        assert chan_peers_3 == chan_peers[0:3]
        assert chan_peers == sorted(chan_peers, key=lambda x: x.last_response, reverse=True)

        # Make sure only the older peers are dropped as excess
        for p in chan_peers:
            assert p.last_response > first_peer_timestamp

        # Test removing a peer directly, e.g. as a result of a query timeout
        peer = Peer(default_eccrypto.generate_key("very-low"), ("1.2.3.4", 5))
        mapping.add(peer, chan_pk, chan_id)
        mapping.remove_peer(peer)
        for p in chan_peers:
            mapping.remove_peer(p)

        assert mapping.get_last_seen_peers_for_channel(chan_pk, chan_id) == []

        # Make sure the stuff is cleaned up
        assert len(mapping._peers_channels) == 0
        assert len(mapping._channels_dict) == 0

    async def test_get_known_subscribed_peers_for_node(self):
        key = default_eccrypto.generate_key("curve25519")
        with db_session:
            channel = self.overlay(0).mds.ChannelMetadata(origin_id=0, infohash=random_infohash(), sign_with=key)
            folder1 = self.overlay(0).mds.CollectionNode(origin_id=channel.id_, sign_with=key)
            folder2 = self.overlay(0).mds.CollectionNode(origin_id=folder1.id_, sign_with=key)

            orphan = self.overlay(0).mds.CollectionNode(origin_id=123123, sign_with=key)

        source_peer = self.nodes[1].my_peer
        self.overlay(0).channels_peers.add(source_peer, channel.public_key, channel.id_)
        assert [source_peer] == self.overlay(0).get_known_subscribed_peers_for_node(channel.public_key, channel.id_)
        assert [source_peer] == self.overlay(0).get_known_subscribed_peers_for_node(folder1.public_key, folder1.id_)
        assert [source_peer] == self.overlay(0).get_known_subscribed_peers_for_node(folder2.public_key, folder2.id_)
        assert [] == self.overlay(0).get_known_subscribed_peers_for_node(orphan.public_key, orphan.id_)

    async def test_remote_search_mapped_peers(self):
        """
        Test using mapped peers for channel queries.
        """
        key = default_eccrypto.generate_key("curve25519")
        channel_pk = key.pub().key_to_bin()[10:]
        channel_id = 123
        kwargs = {"channel_pk": channel_pk, "origin_id": channel_id}

        await self.introduce_nodes()

        source_peer = self.nodes[2].overlay.get_peers()[0]
        self.nodes[2].overlay.channels_peers.add(source_peer, channel_pk, channel_id)

        self.nodes[2].overlay.notifier = None

        # We disable getting random peers, so the only source for peers is channels peers map
        self.nodes[2].overlay.get_random_peers = lambda _: []

        self.nodes[2].overlay.send_remote_select = Mock()
        self.nodes[2].overlay.send_search_request(**kwargs)

        # The peer must have queried at least one peer
        self.nodes[2].overlay.send_remote_select.assert_called()

    async def test_drop_silent_peer_from_channels_map(self):
        # We do not want the query back mechanism to interfere with this test
        self.nodes[1].overlay.rqc_settings.max_channel_query_back = 0
        kwargs_dict = {"txt_filter": "ubuntu*"}
        with patch(f'{BASE_PATH}.SelectRequest.timeout_delay', new_callable=PropertyMock) as delay_mock:
            # Change query timeout to a really low value
            delay_mock.return_value = 0.3

            # Stop peer 0 from responding
            with patch(f'{BASE_PATH}.RemoteQueryCommunity._on_remote_select_basic'):
                self.nodes[1].overlay.channels_peers.remove_peer = Mock()
                self.nodes[1].overlay.send_remote_select(self.nodes[0].my_peer, **kwargs_dict)

                await self.deliver_messages(timeout=1)
                # node 0 must have called remove_peer because of the timeout
                self.nodes[1].overlay.channels_peers.remove_peer.assert_called()

            # Now test that even in the case of an empty response packet, remove_peer is not called on timeout
            self.nodes[1].overlay.channels_peers.remove_peer = Mock()
            self.nodes[1].overlay.send_remote_select(self.nodes[0].my_peer, **kwargs_dict)
            await self.deliver_messages(timeout=1)
            self.nodes[1].overlay.channels_peers.remove_peer.assert_not_called()

    async def test_remote_select_channel_contents(self):
        """
        Test awaiting for response from remote peer
        """
        client, server, kwargs = self.client_server_request_setup()
        with db_session:
            results = [p.to_simple_dict() for p in server.mds.get_entries(**kwargs)]
        assert results == await client.remote_select_channel_contents(**kwargs)
        assert len(results) == 50

    async def test_remote_select_channel_contents_empty(self):
        """
        Test awaiting for response from remote peer and getting empty results
        """
        client, _, kwargs = self.client_server_request_setup()
        kwargs["origin_id"] = 333
        assert [] == await client.remote_select_channel_contents(**kwargs)

    async def test_remote_select_channel_timeout(self):
        client, server, kwargs = self.client_server_request_setup()
        server.send_db_results = Mock()
        with patch(f'{BASE_PATH}.EvaSelectRequest.timeout_delay', new_callable=PropertyMock) as zz:
            zz.return_value = 2.0
            with pytest.raises(RequestTimeoutException):
                await client.remote_select_channel_contents(**kwargs)

    async def test_remote_select_channel_no_peers(self):
        client, _, kwargs = self.client_server_request_setup()
        client.get_known_subscribed_peers_for_node = lambda *_: []
        with pytest.raises(NoChannelSourcesException):
            await client.remote_select_channel_contents(**kwargs)

    async def test_remote_select_channel_contents_happy_eyeballs(self):
        """
        Test trying to connect to the first server, then timing out and falling back to the second one
        """
        client, server1, server2, kwargs_server2 = self.double_client_server_request_setup()
        with db_session:
            results = [p.to_simple_dict() for p in server2.mds.get_entries(**kwargs_server2)]

        # Force the first server to remain silent
        server1._on_remote_select_basic = AsyncMock()

        # Check that the results came from the second server
        assert results == await client.remote_select_channel_contents(**kwargs_server2)
        assert len(results) == 50

        # Check that the first server actually received a call
        server1._on_remote_select_basic.assert_called_once()
