from ipv8.keyvault.crypto import default_eccrypto

from pony.orm import db_session

import pytest

from tribler_core.modules.metadata_store.orm_bindings.channel_node import NEW
from tribler_core.utilities.random_utils import random_infohash


@pytest.fixture
def add_fake_torrents_channels(session):
    infohashes = []

    torrents_per_channel = 5
    # Add a few channels
    with db_session:
        for ind in range(10):
            ext_key = default_eccrypto.generate_key('curve25519')
            channel = session.mds.ChannelMetadata(
                title='channel%d' % ind,
                subscribed=(ind % 2 == 0),
                num_entries=torrents_per_channel,
                infohash=random_infohash(),
                id_=123,
                sign_with=ext_key,
                version=10,
                local_version=(ind % 11),
            )
            for torrent_ind in range(torrents_per_channel):
                rand_infohash = random_infohash()
                infohashes.append(rand_infohash)
                session.mds.TorrentMetadata(
                    origin_id=channel.id_, title='torrent%d' % torrent_ind, infohash=rand_infohash, sign_with=ext_key
                )


@pytest.fixture
def my_channel(session):
    with db_session:
        chan = session.mds.ChannelMetadata.create_channel('test', 'test')
        for ind in range(5):
            _ = session.mds.TorrentMetadata(
                origin_id=chan.id_, title='torrent%d' % ind, status=NEW, infohash=random_infohash()
            )
        for ind in range(5, 9):
            _ = session.mds.TorrentMetadata(origin_id=chan.id_, title='torrent%d' % ind, infohash=random_infohash())

        chan2 = session.mds.ChannelMetadata.create_channel('test2', 'test2')
        for ind in range(5):
            _ = session.mds.TorrentMetadata(
                origin_id=chan2.id_, title='torrentB%d' % ind, status=NEW, infohash=random_infohash()
            )
        for ind in range(5, 9):
            _ = session.mds.TorrentMetadata(origin_id=chan2.id_, title='torrentB%d' % ind, infohash=random_infohash())
        return chan
