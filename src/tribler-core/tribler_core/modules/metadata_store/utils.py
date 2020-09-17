from ipv8.keyvault.crypto import default_eccrypto

from pony.orm import db_session

from tribler_core.utilities.random_utils import random_infohash, random_utf8_string


@db_session
def generate_torrent(metadata_store, parent):
    metadata_store.TorrentMetadata(title=random_utf8_string(50), infohash=random_infohash(), origin_id=parent.id_)


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
    for _ in range(0, 3):
        generate_collection(metadata_store, chan1)
    chan1.commit_channel_torrent()

    chan2 = metadata_store.ChannelMetadata.create_channel(title="personal channel " + random_utf8_string(50))
    for _ in range(0, 3):
        generate_collection(metadata_store, chan2)

    # add 'Tribler' entry to facilitate keyword search tests
    generate_channel(metadata_store, title="Tribler tribler chan", subscribed=True)
