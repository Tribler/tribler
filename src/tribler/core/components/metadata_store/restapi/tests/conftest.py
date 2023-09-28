import hashlib
from time import time

import pytest
from ipv8.keyvault.crypto import default_eccrypto
from pony.orm import db_session

from tribler.core.components.metadata_store.db.orm_bindings.channel_node import NEW
from tribler.core.components.metadata_store.utils import tag_torrent
from tribler.core.utilities.utilities import random_infohash


@db_session
def create_channel(metadata_store, title, torrents_per_channel=5, local_version=0, subscribed=True):
    def sha1_hash(value: str) -> bytes:
        return hashlib.sha1(value.encode('utf-8')).digest()

    def add_torrent_to_channel(torrent_title, seeders, self_checked):
        t = metadata_store.TorrentMetadata(origin_id=channel.id_, title=torrent_title,
                                           infohash=sha1_hash(torrent_title), sign_with=key)
        t.health.seeders = seeders
        t.health.self_checked = self_checked

        one_week = 60 * 60 * 24 * 7
        now = int(time())

        t.health.last_check = now - one_week if self_checked else now

    key = default_eccrypto.generate_key('curve25519')

    channel = metadata_store.ChannelMetadata(title=title, subscribed=subscribed,
                                             num_entries=torrents_per_channel,
                                             infohash=sha1_hash(title), id_=123,
                                             sign_with=key, version=10,
                                             local_version=local_version)

    for torrent_i in range(torrents_per_channel):
        add_torrent_to_channel(f'torrent{channel.title}{torrent_i}', seeders=torrent_i,
                               self_checked=bool(torrent_i % 2))


@pytest.fixture
def add_subscribed_and_not_downloaded_channel(metadata_store):
    create_channel(metadata_store, 'Subscribed and not downloaded', subscribed=True, local_version=0)


@pytest.fixture
def add_fake_torrents_channels(metadata_store):
    for i in range(10):
        create_channel(metadata_store, f'channel{i}', subscribed=bool(i % 2), local_version=i)


@pytest.fixture
def my_channel(metadata_store, tribler_db):
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
            tag_torrent(infohash, tribler_db)
        for ind in range(5, 9):
            infohash = random_infohash()
            _ = metadata_store.TorrentMetadata(origin_id=chan.id_, title='torrent%d' % ind, infohash=infohash)
            tag_torrent(infohash, tribler_db)

        chan2 = metadata_store.ChannelMetadata.create_channel('test2', 'test2')
        for ind in range(5):
            infohash = random_infohash()
            _ = metadata_store.TorrentMetadata(
                origin_id=chan2.id_, title='torrentB%d' % ind, status=NEW, infohash=infohash
            )
            tag_torrent(infohash, tribler_db)
        for ind in range(5, 9):
            infohash = random_infohash()
            _ = metadata_store.TorrentMetadata(
                origin_id=chan2.id_, title='torrentB%d' % ind, infohash=random_infohash()
            )
            tag_torrent(infohash, tribler_db)
        return chan
