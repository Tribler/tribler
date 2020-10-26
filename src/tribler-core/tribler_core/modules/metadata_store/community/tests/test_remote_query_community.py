from ipv8.keyvault.crypto import default_eccrypto
from ipv8.peer import Peer
from ipv8.test.base import TestBase

from pony.orm import db_session

from tribler_common.simpledefs import NTFY

from tribler_core.modules.metadata_store.community.remote_query_community import RemoteQueryCommunity, sanitize_query
from tribler_core.modules.metadata_store.orm_bindings.channel_node import NEW
from tribler_core.modules.metadata_store.serialization import CHANNEL_TORRENT, REGULAR_TORRENT
from tribler_core.modules.metadata_store.store import MetadataStore
from tribler_core.notifier import Notifier
from tribler_core.utilities.path_util import Path
from tribler_core.utilities.random_utils import random_infohash, random_string
from tribler_core.utilities.unicode import hexlify


def add_random_torrent(metadata_cls, name="test", channel=None):
    d = {"infohash": random_infohash(), "title": name, "tags": "", "size": 1234, "status": NEW}
    if channel:
        d.update({"origin_id": channel.id_})
    torrent_metadata = metadata_cls.from_dict(d)
    torrent_metadata.sign()


class TestRemoteQueryCommunity(TestBase):
    """
    Unit tests for the GigaChannel community which do not need a real Session.
    """

    def setUp(self):
        super(TestRemoteQueryCommunity, self).setUp()
        self.count = 0
        self.initialize(RemoteQueryCommunity, 2)

    def create_node(self, *args, **kwargs):
        metadata_store = MetadataStore(
            Path(self.temporary_directory()) / f"{self.count}.db",
            Path(self.temporary_directory()),
            default_eccrypto.generate_key(u"curve25519"),
            disable_sync=True,
        )
        kwargs['metadata_store'] = metadata_store
        kwargs['notifier'] = Notifier()
        node = super(TestRemoteQueryCommunity, self).create_node(*args, **kwargs)
        self.count += 1
        return node

    async def test_remote_select(self):
        # Fill Node 0 DB with channels and torrents entries
        with db_session:
            channel_uns = self.nodes[0].overlay.mds.ChannelMetadata.create_channel("ubuntu channel unsub", "ubuntu")
            channel_uns.subscribed = False
            channel = self.nodes[0].overlay.mds.ChannelMetadata.create_channel("ubuntu channel", "ubuntu")
            channel_id, channel_pk = channel.id_, channel.public_key
            for i in range(20):
                add_random_torrent(self.nodes[0].overlay.mds.TorrentMetadata, name="ubuntu %s" % i, channel=channel)
            channel.commit_channel_torrent()

        await self.introduce_nodes()
        await self.deliver_messages(timeout=0.5)

        # On introduction, the subscribed channel should be sent, so Node 1's DB should immediately get a channel
        # Node 1 DB is empty. It searches for 'ubuntu'
        with db_session:
            torrents = self.nodes[1].overlay.mds.TorrentMetadata.select()[:]
            self.assertEqual(len(torrents), 1)

        # Node 1 DB is empty. It searches for 'ubuntu'
        with db_session:
            # Clean the db from the previous test
            self.nodes[1].overlay.mds.TorrentMetadata.select().delete()
            torrents = self.nodes[1].overlay.mds.TorrentMetadata.select()[:]
            self.assertEqual(len(torrents), 0)

        kwargs_dict = {"txt_filter": "ubuntu*", "metadata_type": [REGULAR_TORRENT]}
        self.nodes[1].overlay.send_remote_select_to_many(**kwargs_dict)

        await self.deliver_messages(timeout=0.5)

        with db_session:
            torrents0 = self.nodes[0].overlay.mds.MetadataNode.get_entries(**kwargs_dict)
            torrents1 = self.nodes[1].overlay.mds.MetadataNode.get_entries(**kwargs_dict)
            self.assertEqual(len(torrents0), len(torrents1))

        # Now try querying for subscribed "ubuntu" channels
        channels1 = self.nodes[1].overlay.mds.MetadataNode.get_entries(channel_pk=channel_pk, id_=channel_id)
        self.assertEqual(0, len(channels1))
        kwargs_dict = {"txt_filter": "ubuntu*", "metadata_type": [CHANNEL_TORRENT], "subscribed": True}
        self.nodes[1].overlay.send_remote_select_to_many(**kwargs_dict)

        await self.deliver_messages(timeout=0.5)

        with db_session:
            channels1 = self.nodes[1].overlay.mds.MetadataNode.get_entries(channel_pk=channel_pk, id_=channel_id)
            self.assertEqual(1, len(channels1))

    async def test_remote_select_subscribed_channels(self):
        """
        Test querying remote peers for subscribed channels and updating local votes accordingly
        """

        def mock_notify(overlay, args):
            overlay.notified_results = True
            self.assertTrue("results" in args[0])

        self.nodes[1].overlay.notifier = Notifier()
        self.nodes[1].overlay.notifier.notify = lambda sub, args: mock_notify(self.nodes[1].overlay, args)

        with db_session:
            # Create one channel with zero contents, to check that only non-empty channels are served
            self.nodes[0].overlay.mds.ChannelMetadata.create_channel("channel sub", "")
            for _ in range(0, 5):
                chan = self.nodes[0].overlay.mds.ChannelMetadata.create_channel("channel sub", "")
                chan.num_entries = 5
                chan.sign()
            for _ in range(0, 5):
                channel_uns = self.nodes[0].overlay.mds.ChannelMetadata.create_channel("channel unsub", "")
                channel_uns.subscribed = False

        peer = self.nodes[0].my_peer
        self.nodes[1].overlay.send_remote_select_subscribed_channels(peer)

        await self.deliver_messages(timeout=0.5)

        with db_session:
            received_channels = self.nodes[1].overlay.mds.ChannelMetadata.select(lambda g: g.title == "channel sub")
            self.assertEqual(received_channels.count(), 5)
            # Only subscribed channels should have been transported
            received_channels_all = self.nodes[1].overlay.mds.ChannelMetadata.select()
            self.assertEqual(received_channels_all.count(), 5)

            # Make sure the subscribed channels transport counted as voting
            self.assertEqual(
                self.nodes[1].overlay.mds.ChannelPeer.select().first().public_key, peer.public_key.key_to_bin()[10:]
            )
            for chan in self.nodes[1].overlay.mds.ChannelMetadata.select():
                self.assertTrue(chan.votes > 0.0)

        # Check that the notifier callback is called on new channel entries
        self.assertTrue(self.nodes[1].overlay.notified_results)

    async def test_remote_select_packets_limit(self):
        """
        Test dropping packets that go over the response limit for a remote select.

        """
        with db_session:
            for _ in range(0, 100):
                self.nodes[0].overlay.mds.ChannelMetadata.create_channel(random_string(100), "")

        peer = self.nodes[0].my_peer
        kwargs_dict = {"metadata_type": [CHANNEL_TORRENT]}
        self.nodes[1].overlay.send_remote_select(peer, **kwargs_dict)
        # There should be an outstanding request in the list
        self.assertTrue(self.nodes[1].overlay.request_cache._identifiers)

        await self.deliver_messages(timeout=0.5)

        with db_session:
            received_channels = self.nodes[1].overlay.mds.ChannelMetadata.select()
            # We should receive less that 6 packets, so all the channels should not fit there.
            self.assertTrue(40 < received_channels.count() < 60)

            # The list of outstanding requests should be empty
            self.assertFalse(self.nodes[1].overlay.request_cache._identifiers)

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
        self.assertIn(peer.mid, self.nodes[1].overlay.queried_subscribed_channels_peers)
        self.assertTrue(send_ok)

        # Make sure the same peer will not be queried twice in case the walker returns to it
        self.nodes[1].overlay.introduction_response_callback(peer, None, None)
        self.assertEqual(len(send_ok), 1)

        # Test clearing queried peers set when it outgrows its capacity
        self.nodes[1].overlay.queried_peers_limit = 2
        self.nodes[1].overlay.introduction_response_callback(Peer(default_eccrypto.generate_key("low")), None, None)
        self.assertEqual(len(self.nodes[1].overlay.queried_subscribed_channels_peers), 2)

        self.nodes[1].overlay.introduction_response_callback(Peer(default_eccrypto.generate_key("low")), None, None)
        self.assertEqual(len(self.nodes[1].overlay.queried_subscribed_channels_peers), 1)

    def test_sanitize_query(self):
        req_response_list = [
            ({"first": None, "last": None}, {"first": 0, "last": 100}),
            ({"first": 123, "last": None}, {"first": 123, "last": 223}),
            ({"first": None, "last": 1000}, {"first": 0, "last": 100}),
            ({"first": 100, "last": None}, {"first": 100, "last": 200}),
            ({}, {"first": 0, "last": 100}),
        ]
        for req, resp in req_response_list:
            self.assertDictEqual(sanitize_query(req), resp)

    def test_sanitize_query_infohash(self):
        infohash_in_b = b'0' * 20
        infohash_in_hex = hexlify(infohash_in_b)

        query = {'infohash': infohash_in_hex}
        sanitize_query(query)
        assert query['infohash'] == infohash_in_b

        # assert no exception raises when 'infohash' is missed
        sanitize_query({})

    async def test_infohash_select(self):
        db1 = self.nodes[0].overlay.mds.TorrentMetadata
        db2 = self.nodes[1].overlay.mds.TorrentMetadata

        torrent_infohash = b'0' * 20
        torrent_title = 'title'

        def has_testing_infohash(t):
            return t.infohash == torrent_infohash

        with db_session:
            db1.from_dict({"infohash": torrent_infohash, "title": torrent_title}).sign()

            torrent_has_been_added_to_db1 = db1.select(has_testing_infohash).count() == 1
            torrent_not_presented_on_db2 = db2.select(has_testing_infohash).count() == 0

        assert torrent_has_been_added_to_db1
        assert torrent_not_presented_on_db2

        remote_query = {"infohash": hexlify(torrent_infohash)}
        self.nodes[1].overlay.send_remote_select_to_many(**remote_query)

        await self.deliver_messages(timeout=0.5)
        with db_session:
            torrents = list(db2.select(has_testing_infohash))

        torrent_is_presented_on_db2 = len(torrents) == 1
        torrent_has_valid_title = torrents[0].title == torrent_title

        assert torrent_is_presented_on_db2
        assert torrent_has_valid_title

    async def add_unknown_torrent(self, enabled):
        rqc1 = self.nodes[0].overlay
        rqc2 = self.nodes[1].overlay

        rqc1.enable_resolve_unknown_torrents_feature = enabled
        rqc2.enable_resolve_unknown_torrents_feature = enabled

        db1 = rqc1.mds.TorrentMetadata
        db2 = rqc2.mds.TorrentMetadata

        torrent_infohash = random_infohash()

        def has_testing_infohash(t):
            return t.infohash == torrent_infohash

        with db_session:
            db1.from_dict({"infohash": torrent_infohash, "title": 'title'}).sign()

            torrent_has_been_added_to_db1 = db1.select(has_testing_infohash).count() == 1
            torrent_not_presented_on_db2 = db2.select(has_testing_infohash).count() == 0

        assert torrent_has_been_added_to_db1
        assert torrent_not_presented_on_db2

        # notify second node that new torrent hash has been received from the first node
        rqc2.notifier.notify(NTFY.POPULARITY_COMMUNITY_ADD_UNKNOWN_TORRENT,
                             self.nodes[0].my_peer,
                             torrent_infohash)

        await self.deliver_messages(timeout=0.5)
        with db_session:
            torrent_is_presented_on_db2 = db2.select(has_testing_infohash).count() == 1

        if rqc2.enable_resolve_unknown_torrents_feature:
            assert torrent_is_presented_on_db2
        else:
            assert not torrent_is_presented_on_db2

    async def test_add_unknown_torrent(self):
        await self.add_unknown_torrent(True)
        await self.add_unknown_torrent(False)

    async def test_unknown_query_attribute(self):
        rqc_node2 = self.nodes[1].overlay

        # only the new attribute
        rqc_node2.send_remote_select_to_many(**{'new_attribute': 'some_value'})
        await self.deliver_messages(timeout=0.1)

        # mixed: the old and a new attribute
        rqc_node2.send_remote_select_to_many(**{'infohash': hexlify(b'0' * 20),
                                                'new_attribute': 'some_value'})
        await self.deliver_messages(timeout=0.1)

        # no exception have been raised
        assert True
