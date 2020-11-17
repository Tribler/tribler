from datetime import datetime

from ipv8.database import database_blob
from ipv8.keyvault.crypto import default_eccrypto
from ipv8.peer import Peer
from ipv8.test.base import TestBase

from pony.orm import db_session

from tribler_core.modules.metadata_store.community.gigachannel_community import GigaChannelCommunity
from tribler_core.modules.metadata_store.store import MetadataStore
from tribler_core.notifier import Notifier
from tribler_core.utilities.path_util import Path
from tribler_core.utilities.random_utils import random_infohash

EMPTY_BLOB = database_blob(b"")


class TestGigaChannelUnits(TestBase):
    def setUp(self):
        super().setUp()
        self.count = 0
        self.initialize(GigaChannelCommunity, 3)
        self.torrent_template = {"title": "", "infohash": b"", "torrent_date": datetime(1970, 1, 1), "tags": "video"}

    def create_node(self, *args, **kwargs):
        metadata_store = MetadataStore(
            Path(self.temporary_directory()) / f"{self.count}.db",
            Path(self.temporary_directory()),
            default_eccrypto.generate_key(u"curve25519"),
            disable_sync=True,
        )
        kwargs['metadata_store'] = metadata_store
        node = super().create_node(*args, **kwargs)
        self.count += 1
        return node

    def channel_metadata(self, i):
        return self.nodes[i].overlay.mds.ChannelMetadata

    def torrent_metadata(self, i):
        return self.nodes[i].overlay.mds.TorrentMetadata

    async def test_gigachannel_search(self):
        """
        Test searching several nodes for metadata entries based on title text
        """

        # We do not want the query back mechanism and introduction callback to interfere with this test
        for node in self.nodes:
            node.overlay.settings.max_channel_query_back = 0

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
        self.nodes[1].overlay.introduction_response_callback(peer, None, None)
        self.assertIn(peer.mid, self.nodes[1].overlay.queried_peers)
        self.assertTrue(send_ok)

        # Make sure the same peer will not be queried twice in case the walker returns to it
        self.nodes[1].overlay.introduction_response_callback(peer, None, None)
        self.assertEqual(len(send_ok), 1)

        # Test clearing queried peers set when it outgrows its capacity
        self.nodes[1].overlay.settings.queried_peers_limit = 2
        self.nodes[1].overlay.introduction_response_callback(Peer(default_eccrypto.generate_key("low")), None, None)
        self.assertEqual(len(self.nodes[1].overlay.queried_peers), 2)

        self.nodes[1].overlay.introduction_response_callback(Peer(default_eccrypto.generate_key("low")), None, None)
        # The set has been cleared, so the number of queried peers must be dropped back to 1
        self.assertEqual(len(self.nodes[1].overlay.queried_peers), 1)

    async def test_remote_select_subscribed_channels(self):
        """
        Test querying remote peers for subscribed channels and updating local votes accordingly.
        """

        # We do not want the query back mechanism to interfere with this test
        self.nodes[1].overlay.settings.max_channel_query_back = 0

        num_channels = 5

        with db_session:
            # Create one channel with zero contents, to check that only non-empty channels are served
            self.nodes[0].overlay.mds.ChannelMetadata.create_channel("channel sub", "")
            for _ in range(0, num_channels):
                chan = self.nodes[0].overlay.mds.ChannelMetadata.create_channel("channel sub", "")
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

        # TODO: query only "complete" channels

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
