from time import time

from ipv8.keyvault.crypto import default_eccrypto

from pony.orm import db_session

import pytest

from tribler_core.components.metadata_store.db.orm_bindings.channel_node import NEW
from tribler_core.components.metadata_store.utils import tag_torrent
from tribler_core.utilities.random_utils import random_infohash


@pytest.fixture
def add_fake_torrents_channels(metadata_store):
    infohashes = []

    torrents_per_channel = 5
    # Add a few channels
    with db_session:
        for ind in range(10):
            ext_key = default_eccrypto.generate_key('curve25519')
            channel = metadata_store.ChannelMetadata(
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
                t = metadata_store.TorrentMetadata(
                    origin_id=channel.id_, title='torrent%d' % torrent_ind, infohash=rand_infohash, sign_with=ext_key
                )
                t.health.seeders = int.from_bytes(t.infohash[:2], byteorder="big")
                t.health.self_checked = bool(torrent_ind % 2 == 1)
                t.health.last_check = int(time()) - (60 * 60 * 24 * 7 if torrent_ind % 2 else 0)


@pytest.fixture
def my_channel(metadata_store, tags_db):
    """
    Generate a channel with some torrents. Also add a few (random) tags to these torrents.
    """
    with db_session:
        chan = metadata_store.ChannelMetadata.create_channel('test', 'test')
        for ind in range(5):
            infohash = random_infohash()
            _ = metadata_store.TorrentMetadata(
                origin_id=chan.id_, title='torrent%d' % ind, status=NEW, infohash=infohash
            )
            tag_torrent(infohash, tags_db)
        for ind in range(5, 9):
            infohash = random_infohash()
            _ = metadata_store.TorrentMetadata(origin_id=chan.id_, title='torrent%d' % ind, infohash=infohash)
            tag_torrent(infohash, tags_db)

        chan2 = metadata_store.ChannelMetadata.create_channel('test2', 'test2')
        for ind in range(5):
            infohash = random_infohash()
            _ = metadata_store.TorrentMetadata(
                origin_id=chan2.id_, title='torrentB%d' % ind, status=NEW, infohash=infohash
            )
            tag_torrent(infohash, tags_db)
        for ind in range(5, 9):
            infohash = random_infohash()
            _ = metadata_store.TorrentMetadata(
                origin_id=chan2.id_, title='torrentB%d' % ind, infohash=random_infohash()
            )
            tag_torrent(infohash, tags_db)
        return chan
