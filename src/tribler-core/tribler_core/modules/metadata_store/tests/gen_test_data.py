import os
import random
from datetime import datetime

from ipv8.keyvault.crypto import default_eccrypto

from pony.orm import db_session

from tribler_core.modules.libtorrent.torrentdef import TorrentDef
from tribler_core.modules.metadata_store.orm_bindings.channel_node import NEW
from tribler_core.modules.metadata_store.store import MetadataStore
from tribler_core.modules.metadata_store.tests.test_channel_download import (
    CHANNEL_METADATA,
    CHANNEL_METADATA_UPDATED,
    CHANNEL_TORRENT,
    CHANNEL_TORRENT_UPDATED,
)
from tribler_core.tests.tools.common import TORRENT_UBUNTU_FILE, TORRENT_VIDEO_FILE
from tribler_core.utilities.path_util import Path

DATA_DIR = Path(__file__).parent / '..' / '..' / 'data'
SAMPLE_DIR = DATA_DIR / 'sample_channel'

my_key = default_eccrypto.generate_key(u"curve25519")


ALL_PRINTABLE_CHARS = ''.join(tuple(chr(i) for i in range(32, 0x110000) if chr(i).isprintable()))


def get_random_text_string(size=200):
    return "".join(random.sample(ALL_PRINTABLE_CHARS, size))


def gen_random_entry():
    return {
        "title": "test entry " + str(random.randint(0, 1000000)),
        "infohash": str(random.getrandbits(160)),
        "torrent_date": datetime(1970, 1, 1),
        "size": 100 + random.randint(0, 10000),
        "tags": "video",
        "status": NEW,
    }


@db_session
def gen_sample_channel(mds):
    my_channel = mds.ChannelMetadata.create_channel('test_channel', 'test description')

    my_channel.add_torrent_to_channel(TorrentDef.load(TORRENT_UBUNTU_FILE), None)
    my_channel.commit_channel_torrent()

    t2 = my_channel.add_torrent_to_channel(TorrentDef.load(TORRENT_VIDEO_FILE), None)
    mds.TorrentMetadata.from_dict(dict(origin_id=my_channel.id_, **gen_random_entry()))
    mds.TorrentMetadata.from_dict(dict(origin_id=my_channel.id_, **gen_random_entry()))
    coll = mds.CollectionNode(origin_id=my_channel.id_, title='internal collection')
    mds.TorrentMetadata.from_dict(dict(origin_id=coll.id_, **gen_random_entry()))
    mds.TorrentMetadata.from_dict(dict(origin_id=coll.id_, **gen_random_entry()))
    my_channel.commit_channel_torrent()

    t2.soft_delete()
    my_channel.commit_channel_torrent()

    # Rename files to stable names
    mdblob_name = SAMPLE_DIR / (my_channel.dirname + ".mdblob")
    torrent_name = SAMPLE_DIR / (my_channel.dirname + ".torrent")

    os.rename(mdblob_name, CHANNEL_METADATA)
    os.rename(torrent_name, CHANNEL_TORRENT)

    # Update channel
    mds.TorrentMetadata.from_dict(dict(origin_id=my_channel.id_, **gen_random_entry()))
    my_channel.commit_channel_torrent()

    # Rename updated files to stable names
    os.rename(mdblob_name, CHANNEL_METADATA_UPDATED)
    os.rename(torrent_name, CHANNEL_TORRENT_UPDATED)


if __name__ == "__main__":
    mds = MetadataStore(":memory:", SAMPLE_DIR, my_key)
    gen_sample_channel(mds)
