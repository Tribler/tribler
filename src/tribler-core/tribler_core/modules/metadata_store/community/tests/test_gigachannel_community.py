from ipv8.database import database_blob
from ipv8.keyvault.crypto import default_eccrypto
from ipv8.peer import Peer
from ipv8.test.base import TestBase

from pony.orm import db_session

from tribler_core.modules.metadata_store.community.gigachannel_community import GigaChannelCommunity
from tribler_core.modules.metadata_store.orm_bindings.channel_node import LEGACY_ENTRY, NEW
from tribler_core.modules.metadata_store.serialization import REGULAR_TORRENT
from tribler_core.modules.metadata_store.store import MetadataStore
from tribler_core.tests.tools.base_test import MockObject
from tribler_core.utilities.path_util import Path
from tribler_core.utilities.random_utils import random_infohash

EMPTY_BLOB = database_blob(b"")


class TestGigaChannelUnits(TestBase):
    """
    Unit tests for the GigaChannel community which do not need a real Session.
    """

    def setUp(self):
        super(TestGigaChannelUnits, self).setUp()
        self.count = 0
        self.initialize(GigaChannelCommunity, 2)

    def create_node(self, *args, **kwargs):
        metadata_store = MetadataStore(
            Path(self.temporary_directory()) / ("%d.db" % self.count),
            Path(self.temporary_directory()),
            default_eccrypto.generate_key(u"curve25519"),
        )
        kwargs['metadata_store'] = metadata_store
        node = super(TestGigaChannelUnits, self).create_node(*args, **kwargs)
        self.count += 1
        return node

    def add_random_torrent(self, metadata_cls, name="test", channel=None):
        d = {"infohash": random_infohash(), "title": name, "tags": "", "size": 1234, "status": NEW}
        if channel:
            d.update({"origin_id": channel.id_})
        torrent_metadata = metadata_cls.from_dict(d)
        torrent_metadata.sign()

    async def test_send_random_subscribed_channel(self):
        """
        Test whether sending a single channel with a single torrent to another peer works correctly
        """
        with db_session:
            channel = self.nodes[0].overlay.metadata_store.ChannelMetadata.create_channel("test", "bla")
            self.add_random_torrent(self.nodes[0].overlay.metadata_store.TorrentMetadata, channel=channel)
            channel.commit_channel_torrent()
        # We must change the key for the first node so the created channel becomes foreign
        self.nodes[0].overlay.metadata_store.ChannelNode._my_key = default_eccrypto.generate_key(u"curve25519")
        await self.nodes[0].overlay.prepare_gossip_blob_cache()

        self.nodes[0].overlay.send_random_to(Peer(self.nodes[1].my_peer.public_key, self.nodes[1].endpoint.wan_address))
        await self.deliver_messages(timeout=0.5)
        with db_session:
            self.assertEqual(len(self.nodes[1].overlay.metadata_store.ChannelMetadata.select()), 1)
            channel = self.nodes[1].overlay.metadata_store.ChannelMetadata.select()[:][0]
            self.assertEqual(channel.contents_len, 1)

    async def test_send_random_personal_channel(self):
        """
        Test whether sending the personal channel works correctly
        """
        with db_session:
            channel = self.nodes[0].overlay.metadata_store.ChannelMetadata.create_channel("test", "bla")
            self.add_random_torrent(self.nodes[0].overlay.metadata_store.TorrentMetadata, channel=channel)
            channel.commit_channel_torrent()

        await self.nodes[0].overlay.prepare_gossip_blob_cache()
        self.nodes[0].overlay.send_random_to(Peer(self.nodes[1].my_peer.public_key, self.nodes[1].endpoint.wan_address))

        await self.deliver_messages(timeout=0.5)

        with db_session:
            self.assertEqual(len(self.nodes[1].overlay.metadata_store.ChannelMetadata.select()), 1)
            channel = self.nodes[1].overlay.metadata_store.ChannelMetadata.select()[:][0]
            self.assertEqual(channel.contents_len, 1)

    async def test_send_personal_and_random_channels(self):
        """
        Test whether sending the personal channel works correctly
        """
        with db_session:
            # Add non-personal channel
            channel = self.nodes[0].overlay.metadata_store.ChannelMetadata.create_channel("non-personal", "bla")
            self.add_random_torrent(self.nodes[0].overlay.metadata_store.TorrentMetadata, channel=channel)
            channel.commit_channel_torrent()

            # Add personal channel
            self.nodes[0].overlay.metadata_store.ChannelNode._my_key = default_eccrypto.generate_key(u"curve25519")
            # After the previous line the previously created channel becomes non-personal
            channel = self.nodes[0].overlay.metadata_store.ChannelMetadata.create_channel("personal", "bla")
            self.add_random_torrent(self.nodes[0].overlay.metadata_store.TorrentMetadata, channel=channel)
            channel.commit_channel_torrent()

        await self.nodes[0].overlay.prepare_gossip_blob_cache()
        self.nodes[0].overlay.send_random_to(Peer(self.nodes[1].my_peer.public_key, self.nodes[1].endpoint.wan_address))
        await self.deliver_messages(timeout=0.5)
        with db_session:
            self.assertEqual(len(self.nodes[1].overlay.metadata_store.ChannelMetadata.select()), 2)
            channels = self.nodes[1].overlay.metadata_store.ChannelMetadata.select()[:]
            self.assertEqual(channels[0].contents_len, 1)
            self.assertEqual(channels[1].contents_len, 1)

    async def test_send_random_multiple_torrents(self):
        """
        Test whether sending a single channel with a multiple torrents to another peer works correctly
        """
        with db_session:
            channel = self.nodes[0].overlay.metadata_store.ChannelMetadata.create_channel("test", "bla")
            for _ in range(10):
                self.add_random_torrent(self.nodes[0].overlay.metadata_store.TorrentMetadata, channel=channel)
            channel.commit_channel_torrent()

        await self.nodes[0].overlay.prepare_gossip_blob_cache()
        self.nodes[0].overlay.send_random_to(Peer(self.nodes[1].my_peer.public_key, self.nodes[1].endpoint.wan_address))

        await self.deliver_messages(timeout=0.5)

        with db_session:
            channel = self.nodes[1].overlay.metadata_store.ChannelMetadata.get()
            torrents1 = self.nodes[1].overlay.metadata_store.TorrentMetadata.select()[:]
            self.assertLess(channel.contents_len, 10)
            self.assertLess(0, channel.contents_len)

        # We must delete the old and create all-new torrent entries for the next test.
        # Otherwise, it becomes non-deterministic.
        with db_session:
            channel = self.nodes[0].overlay.metadata_store.ChannelMetadata.get()
            self.nodes[0].overlay.metadata_store.TorrentMetadata.select(
                lambda g: g.metadata_type == REGULAR_TORRENT
            ).delete()
            self.nodes[1].overlay.metadata_store.TorrentMetadata.select().delete()

            for _ in range(10):
                self.add_random_torrent(self.nodes[0].overlay.metadata_store.TorrentMetadata, channel=channel)
            channel.commit_channel_torrent()

        # Initiate the gossip again. This time, it should be sent from the blob cache
        # so the torrents on the receiving end should not change this time.
        self.nodes[0].overlay.send_random_to(Peer(self.nodes[1].my_peer.public_key, self.nodes[1].endpoint.wan_address))

        await self.deliver_messages(timeout=0.5)
        with db_session:
            torrents2 = self.nodes[1].overlay.metadata_store.TorrentMetadata.select()[:]
            self.assertEqual(len(torrents1), len(torrents2))

        await self.nodes[0].overlay.prepare_gossip_blob_cache()
        self.nodes[0].overlay.send_random_to(Peer(self.nodes[1].my_peer.public_key, self.nodes[1].endpoint.wan_address))

        await self.deliver_messages(timeout=0.5)
        with db_session:
            torrents3 = self.nodes[1].overlay.metadata_store.TorrentMetadata.select()[:]
            self.assertLess(len(torrents2), len(torrents3))

    async def test_send_and_get_channel_update_back(self):
        """
        Test if sending back information on updated version of a channel works
        """
        with db_session:
            # Add channel to node 0
            channel = self.nodes[0].overlay.metadata_store.ChannelMetadata.create_channel("test", "bla")
            for _ in range(20):
                self.add_random_torrent(self.nodes[0].overlay.metadata_store.TorrentMetadata, channel=channel)
            channel.commit_channel_torrent()
            channel_v1_dict = channel.to_dict()
            channel_v1_dict.pop("health")
            self.add_random_torrent(self.nodes[0].overlay.metadata_store.TorrentMetadata, channel=channel)
            channel.commit_channel_torrent()

        with db_session:
            # Add the outdated version of the channel to node 1
            self.nodes[1].overlay.metadata_store.ChannelMetadata.from_dict(channel_v1_dict)

        # node1 --outdated_channel--> node0
        await self.nodes[1].overlay.prepare_gossip_blob_cache()
        self.nodes[1].overlay.send_random_to(Peer(self.nodes[0].my_peer.public_key, self.nodes[0].endpoint.wan_address))

        await self.deliver_messages(timeout=0.5)

        with db_session:
            self.assertEqual(
                self.nodes[1].overlay.metadata_store.ChannelMetadata.select()[:][0].timestamp,
                self.nodes[0].overlay.metadata_store.ChannelMetadata.select()[:][0].timestamp,
            )

    async def test_gigachannel_search(self):
        """
        Scenario: Node 0 is setup with a channel with 20 ubuntu related torrents. Node 1 searches for 'ubuntu' and
        expects to receive some results. The search results are processed by node 1 when it receives and adds to its
        database. Max number of results is 5, so we expect 5 torrents are added the database.
        """

        def mock_notify(overlay, args):
            overlay.notified_results = True
            self.assertTrue("results" in args[0])

        self.nodes[1].overlay.notifier = MockObject()
        self.nodes[1].overlay.notifier.notify = lambda sub, args: mock_notify(self.nodes[1].overlay, args)

        await self.introduce_nodes()

        with db_session:
            # add some free-for-all entries
            self.nodes[0].overlay.metadata_store.TorrentMetadata.add_ffa_from_dict(
                dict(title="ubuntu legacy", infohash=random_infohash())
            )
            self.nodes[0].overlay.metadata_store.ChannelMetadata(
                title="ubuntu legacy chan", infohash=random_infohash(), public_key=b"", status=LEGACY_ENTRY, id_=0
            )
            channel = self.nodes[0].overlay.metadata_store.ChannelMetadata.create_channel("ubuntu", "ubuntu")
            for i in range(20):
                self.add_random_torrent(
                    self.nodes[0].overlay.metadata_store.TorrentMetadata, name="ubuntu %s" % i, channel=channel
                )
            channel.commit_channel_torrent()

        # Node 1 has no torrents and searches for 'ubuntu'
        with db_session:
            torrents = self.nodes[1].overlay.metadata_store.TorrentMetadata.select()[:]
            self.assertEqual(len(torrents), 0)
        self.nodes[1].overlay.send_search_request(u'"ubuntu"*')

        await self.deliver_messages(timeout=0.5)

        with db_session:
            torrents = self.nodes[1].overlay.metadata_store.TorrentMetadata.select()[:]
            self.assertEqual(len(torrents), 5)

            # Only non-legacy FFA torrents should be sent on search
            torrents_ffa = self.nodes[1].overlay.metadata_store.TorrentMetadata.select(
                lambda g: g.public_key == EMPTY_BLOB
            )[:]
            self.assertEqual(len(torrents_ffa), 1)
            # Legacy FFA channel should not be sent
            channels_ffa = self.nodes[1].overlay.metadata_store.ChannelMetadata.select(
                lambda g: g.public_key == EMPTY_BLOB
            )[:]
            self.assertEqual(len(channels_ffa), 0)
        self.assertTrue(self.nodes[1].overlay.notified_results)

    async def test_gigachannel_search_reject_stale_result(self):
        """
        Scenario: If two search requests are sent one after another, the response for the first query becomes stale and
        is rejected.
        """
        await self.introduce_nodes()

        with db_session:
            channel = self.nodes[0].overlay.metadata_store.ChannelMetadata.create_channel("linux", "ubuntu")
            for i in range(10):
                self.add_random_torrent(
                    self.nodes[0].overlay.metadata_store.TorrentMetadata, name="ubuntu %s" % i, channel=channel
                )
            for i in range(10):
                self.add_random_torrent(
                    self.nodes[0].overlay.metadata_store.TorrentMetadata, name="debian %s" % i, channel=channel
                )
            channel.commit_channel_torrent()

        # Assert Node 1 has no previous torrents in the database
        with db_session:
            torrents = self.nodes[1].overlay.metadata_store.TorrentMetadata.select()[:]
            self.assertEqual(len(torrents), 0)

        # Node 1 sent two consecutive queries
        self.nodes[1].overlay.send_search_request(u'"ubuntu"*')
        self.nodes[1].overlay.send_search_request(u'"debian"*')

        await self.deliver_messages(timeout=0.5)

        # Assert that only the last result is accepted
        with db_session:
            torrents = self.nodes[1].overlay.metadata_store.TorrentMetadata.select()[:]
            self.assertEqual(len(torrents), 5)
            for torrent in torrents:
                self.assertIn("debian", torrent.to_simple_dict()['name'])

    async def test_gigachannel_search_with_no_result(self):
        """
        Test giga channel search which yields no result
        """
        await self.introduce_nodes()

        # Both node 0 and node 1 have no torrents in the database
        with db_session:
            torrents = self.nodes[1].overlay.metadata_store.TorrentMetadata.select()[:]
            torrents2 = self.nodes[1].overlay.metadata_store.TorrentMetadata.select()[:]
            self.assertEqual(len(torrents), 0)
            self.assertEqual(len(torrents2), 0)

        # Node 1 searches for 'A ubuntu'
        query = u'"\xc1 ubuntu"*'
        self.nodes[1].overlay.send_search_request(query)

        await self.deliver_messages(timeout=0.5)

        # Expect no data received in search and nothing processed to the database
        with db_session:
            torrents = self.nodes[1].overlay.metadata_store.TorrentMetadata.select()[:]
            self.assertEqual(len(torrents), 0)
