import os
import random
from datetime import datetime

from pony.orm import db_session

from Tribler.Core.Modules.MetadataStore.OrmBindings.channel_node import NEW
from Tribler.Core.Modules.MetadataStore.store import MetadataStore
from Tribler.Core.TorrentDef import TorrentDef
from Tribler.Test.Core.Modules.MetadataStore.test_channel_download import CHANNEL_METADATA, CHANNEL_TORRENT, \
    CHANNEL_TORRENT_UPDATED, CHANNEL_METADATA_UPDATED
from Tribler.Test.common import TORRENT_UBUNTU_FILE, TORRENT_VIDEO_FILE
from Tribler.pyipv8.ipv8.keyvault.crypto import default_eccrypto

DATA_DIR = os.path.join(os.path.abspath(os.path.dirname(os.path.realpath(__file__))), '..', '..', 'data')
SAMPLE_DIR = os.path.join(DATA_DIR, 'sample_channel')

my_key = default_eccrypto.generate_key(u"curve25519")


def gen_random_entry():
    return {
        "title": "test entry " + str(random.randint(0, 1000000)),
        "infohash": str(random.getrandbits(160)),
        "torrent_date": datetime(1970, 1, 1),
        "size": 100 + random.randint(0, 10000),
        "tags": "video",
        "status": NEW
    }


@db_session
def gen_sample_channel(mds):
    my_channel = mds.ChannelMetadata.create_channel('test_channel', 'test description')

    t1 = my_channel.add_torrent_to_channel(TorrentDef.load(TORRENT_UBUNTU_FILE), None)
    my_channel.commit_channel_torrent()

    t2 = my_channel.add_torrent_to_channel(TorrentDef.load(TORRENT_VIDEO_FILE), None)
    t3 = mds.TorrentMetadata.from_dict(gen_random_entry())
    t4 = mds.TorrentMetadata.from_dict(gen_random_entry())
    my_channel.commit_channel_torrent()

    my_channel.delete_torrent(t2.infohash)
    my_channel.commit_channel_torrent()

    # Rename files to stable names
    mdblob_name = os.path.join(SAMPLE_DIR, my_channel.dir_name + ".mdblob")
    torrent_name = os.path.join(SAMPLE_DIR, my_channel.dir_name + ".torrent")

    os.rename(mdblob_name, CHANNEL_METADATA)
    os.rename(torrent_name, CHANNEL_TORRENT)

    # Update channel
    t5 = mds.TorrentMetadata.from_dict(gen_random_entry())
    my_channel.commit_channel_torrent()

    # Rename updated files to stable names
    os.rename(mdblob_name, CHANNEL_METADATA_UPDATED)
    os.rename(torrent_name, CHANNEL_TORRENT_UPDATED)


if __name__ == "__main__":
    mds = MetadataStore(":memory:", SAMPLE_DIR, my_key)
    gen_sample_channel(mds)
