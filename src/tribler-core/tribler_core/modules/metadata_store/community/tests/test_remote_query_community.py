from ipv8.keyvault.crypto import default_eccrypto
from ipv8.test.base import TestBase

from pony.orm import db_session

from tribler_core.modules.metadata_store.community.remote_query_community import RemoteQueryCommunity
from tribler_core.modules.metadata_store.orm_bindings.channel_node import NEW
from tribler_core.modules.metadata_store.serialization import CHANNEL_TORRENT, REGULAR_TORRENT
from tribler_core.modules.metadata_store.store import MetadataStore
from tribler_core.utilities.path_util import Path
from tribler_core.utilities.random_utils import random_infohash


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
        node = super(TestRemoteQueryCommunity, self).create_node(*args, **kwargs)
        self.count += 1
        return node

    async def test_remote_select(self):
        # Fill Node 0 DB with channels and torrents entries
        with db_session:
            channel = self.nodes[0].overlay.mds.ChannelMetadata.create_channel("ubuntu", "ubuntu")
            for i in range(20):
                add_random_torrent(self.nodes[0].overlay.mds.TorrentMetadata, name="ubuntu %s" % i, channel=channel)
            channel.commit_channel_torrent()

        await self.introduce_nodes()

        # Node 1 DB is empty. It searches for 'ubuntu'
        with db_session:
            torrents = self.nodes[1].overlay.mds.TorrentMetadata.select()[:]
            self.assertEqual(len(torrents), 0)

        id_ = 123
        kwargs_dict = {"txt_filter": "ubuntu*", "metadata_type": [CHANNEL_TORRENT, REGULAR_TORRENT]}
        self.nodes[1].overlay.send_remote_select(id_, **kwargs_dict)

        await self.deliver_messages(timeout=0.5)

        with db_session:
            torrents0 = self.nodes[0].overlay.mds.TorrentMetadata.get_entries(**kwargs_dict)
            torrents1 = self.nodes[1].overlay.mds.TorrentMetadata.get_entries(**kwargs_dict)
            self.assertEqual(len(torrents0), len(torrents1))
