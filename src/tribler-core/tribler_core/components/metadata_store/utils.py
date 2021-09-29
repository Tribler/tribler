import random
import time

from ipv8.keyvault.crypto import default_eccrypto

from pony.orm import db_session

from tribler_core.tests.tools.common import PNG_FILE
from tribler_core.utilities.random_utils import random_infohash, random_utf8_string


class RequestTimeoutException(Exception):
    pass


class NoChannelSourcesException(Exception):
    pass


@db_session
def generate_torrent(metadata_store, parent):
    infohash = random_infohash()

    # Give each torrent some health information. For now, we assume all torrents are healthy.
    now = int(time.time())
    last_check = now - random.randint(3600, 24 * 3600)
    torrent_state = metadata_store.TorrentState(infohash=infohash, seeders=10, last_check=last_check)
    metadata_store.TorrentMetadata(title=random_utf8_string(50), infohash=infohash, origin_id=parent.id_,
                                   health=torrent_state)


@db_session
def generate_collection(metadata_store, parent):
    coll = metadata_store.CollectionNode(title=random_utf8_string(50), origin_id=parent.id_)
    for _ in range(0, 3):
        generate_torrent(metadata_store, coll)


@db_session
def generate_channel(metadata_store, title=None, subscribed=False):
    # Remember and restore the original key
    orig_key = metadata_store.ChannelNode._my_key

    metadata_store.ChannelNode._my_key = default_eccrypto.generate_key('low')
    chan = metadata_store.ChannelMetadata(
        title=title or random_utf8_string(100), subscribed=subscribed, infohash=random_infohash()
    )

    # add some collections to the channel
    for _ in range(0, 3):
        generate_collection(metadata_store, chan)

    metadata_store.ChannelNode._my_key = orig_key


@db_session
def generate_test_channels(metadata_store):
    # First, generate some foreign channels
    for ind in range(0, 10):
        generate_channel(metadata_store, subscribed=ind % 2 == 0)

    # This one is necessary to test filters, etc
    generate_channel(metadata_store, title="non-random channel name")

    # The same, but subscribed
    generate_channel(metadata_store, title="non-random subscribed channel name", subscribed=True)

    # Now generate a couple of personal channels
    chan1 = metadata_store.ChannelMetadata.create_channel(title="personal channel with non-random name")

    with open(PNG_FILE, "rb") as f:
        pic_bytes = f.read()
    metadata_store.ChannelThumbnail(binary_data=pic_bytes, data_type="image/png", origin_id=chan1.id_)
    metadata_store.ChannelDescription(json_text='{"description_text": "# Hi guys"}', origin_id=chan1.id_)

    for _ in range(0, 3):
        generate_collection(metadata_store, chan1)
    chan1.commit_channel_torrent()

    chan2 = metadata_store.ChannelMetadata.create_channel(title="personal channel " + random_utf8_string(50))
    for _ in range(0, 3):
        generate_collection(metadata_store, chan2)

    # add 'Tribler' entry to facilitate keyword search tests
    generate_channel(metadata_store, title="Tribler tribler chan", subscribed=True)
