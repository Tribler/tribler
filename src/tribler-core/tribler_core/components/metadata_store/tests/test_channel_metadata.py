import os
from binascii import unhexlify
from datetime import datetime
from itertools import combinations
from pathlib import Path
from unittest.mock import Mock, patch

from ipv8.keyvault.crypto import default_eccrypto

from lz4.frame import LZ4FrameDecompressor

from pony.orm import ObjectNotFound, db_session

import pytest

from tribler_common.simpledefs import CHANNEL_STATE

from tribler_core.components.libtorrent.torrentdef import TorrentDef
from tribler_core.components.metadata_store.db.orm_bindings.channel_metadata import (
    CHANNEL_DIR_NAME_LENGTH,
    MetadataCompressor,
    entries_to_chunk,
)
from tribler_core.components.metadata_store.db.orm_bindings.channel_node import COMMITTED, NEW, TODELETE, UPDATED
from tribler_core.components.metadata_store.db.serialization import (
    CHANNEL_TORRENT,
    COLLECTION_NODE,
    REGULAR_TORRENT,
    int2time,
)
from tribler_core.components.metadata_store.db.store import HealthItemsPayload
from tribler_core.tests.tools.common import TESTS_DATA_DIR, TORRENT_UBUNTU_FILE
from tribler_core.utilities.random_utils import random_infohash

# pylint: disable=protected-access


@pytest.fixture
def my_key():
    return default_eccrypto.generate_key("curve25519")


@pytest.fixture
def torrent_template():
    return {"title": "", "infohash": b"", "torrent_date": datetime(1970, 1, 1), "tags": "video"}


@pytest.fixture
def sample_torrent_dict(my_key):
    return {
        "infohash": b"1" * 20,
        "size": 123,
        "torrent_date": datetime.utcnow(),
        "tags": "bla",
        "id_": 123,
        "public_key": my_key.pub().key_to_bin()[10:],
        "title": "lalala",
    }


@pytest.fixture
def sample_channel_dict(sample_torrent_dict):
    return dict(sample_torrent_dict, votes=222, subscribed=False, timestamp=1)


@pytest.fixture(name='mds_with_some_torrents')
@db_session
def mds_with_some_torrents_fixture(metadata_store):
    # channel1
    #   torrent1 aaa bbb  seeders=10
    #   folder1 aaa ccc
    #   torrent2 bbb aaa  no seeders
    #   torrent3 ccc ddd  seeders=5
    #   folder2 aaa bbb
    #     fodler2_1 aaa bbb
    #     folder2_2 bbb ccc
    #     torrent2_1 aaa ccc  seeders=20
    #   torrent4 ccc ddd  seeders=30
    # channel2
    #   torrent5 aaa zzz  seeders=1
    #   torrent6 aaa zzz

    def save():
        metadata_store._db.flush()  # pylint: disable=W0212

    def new_channel(**kwargs):
        params = dict(subscribed=True, share=True, status=NEW, infohash=random_infohash())
        params.update(kwargs)
        return metadata_store.ChannelMetadata(**params)

    def new_torrent(**kwargs):
        params = dict(origin_id=channel.id_, staus=NEW, infohash=random_infohash())
        params.update(kwargs)
        return metadata_store.TorrentMetadata(**params)

    def new_folder(**kwargs):
        params = dict(origin_id=channel.id_)
        params.update(kwargs)
        return metadata_store.CollectionNode(**params)

    # Prepare some data

    channel = new_channel(title='channel1 aaa bbb')
    save()  # to obtain channel.id_

    new_torrent(title='torrent1 aaa bbb').health.set(seeders=10, leechers=20)
    new_folder(title='folder1 aaa ccc')
    new_torrent(title='torrent2 bbb aaa')
    new_torrent(title='torrent3 ccc ddd').health.set(seeders=5, leechers=10)
    folder2 = new_folder(title='folder2 aaa bbb')
    new_torrent(title='torrent4 ccc ddd').health.set(seeders=30, leechers=40)
    save()  # to obtain folder2.id_
    new_folder(title='folder2_1 aaa bbb', origin_id=folder2.id_)
    new_folder(title='folder2_2 bbb ccc', origin_id=folder2.id_)
    new_torrent(title='torrent2_1 aaa ccc', origin_id=folder2.id_).health.set(seeders=20, leechers=10)
    save()

    key = default_eccrypto.generate_key("curve25519")
    channel2 = new_channel(title='channel2 aaa bbb', sign_with=key)
    save()  # to obtain channel2.id_
    new_torrent(title='torrent5 aaa zzz', origin_id=channel2.id_, sign_with=key).health.set(seeders=1, leechers=2)
    new_torrent(title='torrent6 aaa zzz', origin_id=channel2.id_, sign_with=key)

    return metadata_store, channel


@db_session
def test_serialization(metadata_store):
    """
    Test converting channel metadata to serialized data
    """
    channel_metadata = metadata_store.ChannelMetadata.from_dict({"infohash": random_infohash()})
    assert channel_metadata.serialized()


@db_session
def test_list_contents(metadata_store, torrent_template):
    """
    Test whether a correct list with channel content is returned from the database
    """
    metadata_store.ChannelNode._my_key = default_eccrypto.generate_key('low')
    channel1 = metadata_store.ChannelMetadata(infohash=random_infohash())
    metadata_store.TorrentMetadata.from_dict(dict(torrent_template, origin_id=channel1.id_))

    metadata_store.ChannelNode._my_key = default_eccrypto.generate_key('low')
    channel2 = metadata_store.ChannelMetadata(infohash=random_infohash())
    metadata_store.TorrentMetadata.from_dict(dict(torrent_template, infohash=b"1", origin_id=channel2.id_))
    metadata_store.TorrentMetadata.from_dict(dict(torrent_template, infohash=b"2", origin_id=channel2.id_))

    assert len(channel1.contents_list) == 1
    assert len(channel2.contents_list) == 2
    assert channel2.contents_len == 2


@db_session
def test_get_dirname(sample_channel_dict, metadata_store):
    """
    Test whether the correct directory name is returned for channel metadata
    """
    channel_metadata = metadata_store.ChannelMetadata.from_dict(sample_channel_dict)
    assert len(channel_metadata.dirname) == CHANNEL_DIR_NAME_LENGTH


@db_session
def test_get_channel_with_dirname(sample_channel_dict, metadata_store):
    """
    Test getting a channel with a specific name
    """
    channel_metadata = metadata_store.ChannelMetadata.from_dict(sample_channel_dict)
    dirname = channel_metadata.dirname
    channel_result = metadata_store.ChannelMetadata.get_channel_with_dirname(dirname)
    assert channel_metadata == channel_result

    # Test for corner-case of channel PK starting with zeroes
    channel_metadata.public_key = unhexlify('0' * 128)
    channel_result = metadata_store.ChannelMetadata.get_channel_with_dirname(channel_metadata.dirname)
    assert channel_metadata == channel_result


@db_session
def test_add_metadata_to_channel(torrent_template, metadata_store):
    """
    Test whether adding new torrents to a channel works as expected
    """
    channel_metadata = metadata_store.ChannelMetadata.create_channel('test', 'test')
    original_channel = channel_metadata.to_dict()
    md = metadata_store.TorrentMetadata.from_dict(dict(torrent_template, status=NEW, origin_id=channel_metadata.id_))
    channel_metadata.commit_channel_torrent()

    assert original_channel["timestamp"] < channel_metadata.timestamp
    assert md.timestamp < channel_metadata.timestamp
    assert channel_metadata.num_entries == 1


@db_session
def test_add_torrent_to_channel(metadata_store):
    """
    Test adding a torrent to your channel
    """
    channel_metadata = metadata_store.ChannelMetadata.create_channel('test', 'test')
    tdef = TorrentDef.load(TORRENT_UBUNTU_FILE)
    channel_metadata.add_torrent_to_channel(tdef, {'description': 'blabla'})
    assert channel_metadata.contents_list

    # Make sure trying to add a duplicate torrent does not result in an error
    channel_metadata.add_torrent_to_channel(tdef, None)


@db_session
def test_torrent_exists_in_channel(torrent_template, metadata_store):
    """
    Test torrent already exists in the personal channel.
    """
    channel_metadata = metadata_store.ChannelMetadata.create_channel('test', 'test')
    metadata_store.TorrentMetadata.from_dict(dict(torrent_template, infohash=b"1", origin_id=channel_metadata.id_))
    assert metadata_store.torrent_exists_in_personal_channel(b"1")
    assert not metadata_store.torrent_exists_in_personal_channel(b"0")


@db_session
def test_copy_to_channel(torrent_template, metadata_store):
    """
    Test copying a torrent from an another channel.
    """
    metadata_store.ChannelNode._my_key = default_eccrypto.generate_key('low')
    channel1 = metadata_store.ChannelMetadata(infohash=random_infohash())
    metadata_store.TorrentMetadata.from_dict(dict(torrent_template, infohash=b"1", origin_id=channel1.id_))

    metadata_store.ChannelNode._my_key = default_eccrypto.generate_key('low')
    channel2 = metadata_store.ChannelMetadata(infohash=random_infohash())

    # Trying copying existing torrent to channel
    new_torrent = channel2.copy_torrent_from_infohash(b"1")
    assert new_torrent
    assert len(channel1.contents_list) == 1
    assert len(channel2.contents_list) == 1

    # Try copying non-existing torrent ot channel
    new_torrent2 = channel2.copy_torrent_from_infohash(b"2")
    assert new_torrent2 is None
    assert len(channel1.contents_list) == 1
    assert len(channel2.contents_list) == 1


@db_session
def test_restore_torrent_in_channel(metadata_store):
    """
    Test if the torrent scheduled for deletion is restored/updated after the user tries to re-add it.
    """
    channel_metadata = metadata_store.ChannelMetadata.create_channel('test', 'test')
    tdef = TorrentDef.load(TORRENT_UBUNTU_FILE)
    md = channel_metadata.add_torrent_to_channel(tdef, None)

    # Check correct re-add
    md.status = TODELETE
    md_updated = channel_metadata.add_torrent_to_channel(tdef, None)
    assert UPDATED == md.status
    assert md_updated == md
    assert md.has_valid_signature

    # Check update of torrent properties from a new tdef
    md.status = TODELETE
    new_tracker_address = 'http://tribler.org/announce'
    tdef.torrent_parameters[b'announce'] = new_tracker_address.encode('utf-8')
    md_updated = channel_metadata.add_torrent_to_channel(tdef, None)
    assert md_updated == md
    assert md.status == UPDATED
    assert md.tracker_info == new_tracker_address
    assert md.has_valid_signature
    # In addition, check that the trackers table was properly updated
    assert len(md.health.trackers) == 2


@db_session
def test_delete_torrent_from_channel(metadata_store):
    """
    Test deleting a torrent from your channel
    """
    channel_metadata = metadata_store.ChannelMetadata.create_channel('test', 'test')
    tdef = TorrentDef.load(TORRENT_UBUNTU_FILE)

    # Check that nothing is committed when deleting uncommited torrent metadata
    torrent = channel_metadata.add_torrent_to_channel(tdef, None)
    torrent.soft_delete()
    assert not channel_metadata.contents_list

    # Check append-only deletion process
    torrent = channel_metadata.add_torrent_to_channel(tdef, None)
    channel_metadata.commit_channel_torrent()
    assert len(channel_metadata.contents_list) == 1

    torrent.soft_delete()
    channel_metadata.commit_channel_torrent()
    assert not channel_metadata.contents_list


@db_session
def test_correct_commit_of_delete_entries(metadata_store):
    """
    Test that delete entries are committed to disk within mdblobs with correct filenames.
    GitHub issue #5295
    """

    channel = metadata_store.ChannelMetadata.create_channel('test', 'test')
    # To trigger the bug we must ensure that the deletion commands will not fit in a single mdblob
    with patch.object(metadata_store.ChannelMetadata, "_CHUNK_SIZE_LIMIT", 300):
        torrents = [
            metadata_store.TorrentMetadata(infohash=random_infohash(), origin_id=channel.id_, status=NEW)
            for _ in range(0, metadata_store.ChannelMetadata._CHUNK_SIZE_LIMIT * 2 // 100)
        ]
        channel.commit_channel_torrent()
        for t in torrents:
            t.soft_delete()
        channel.commit_channel_torrent()

        torrents = [
            metadata_store.TorrentMetadata(infohash=random_infohash(), origin_id=channel.id_, status=NEW)
            for _ in range(0, metadata_store.ChannelMetadata._CHUNK_SIZE_LIMIT * 2 // 100)
        ]
        channel.commit_channel_torrent()
        torrents.append(metadata_store.TorrentMetadata(infohash=random_infohash(), origin_id=channel.id_, status=NEW))
        for t in torrents[:-1]:
            t.soft_delete()
        channel.commit_channel_torrent()


@pytest.mark.freeze_time('2021-09-24')
@db_session
def test_vsids(metadata_store, freezer):
    """
    Test VSIDS-based channel popularity system.
    """
    peer_key = default_eccrypto.generate_key("curve25519")
    assert metadata_store.Vsids[0].bump_amount == 1.0

    channel = metadata_store.ChannelMetadata.create_channel('test', 'test')
    metadata_store.vote_bump(channel.public_key, channel.id_, peer_key.pub().key_to_bin()[10:])
    freezer.move_to('2021-09-25')
    metadata_store.vote_bump(channel.public_key, channel.id_, peer_key.pub().key_to_bin()[10:])
    assert channel.votes > 0.0
    assert metadata_store.Vsids[0].bump_amount > 1.0

    # Make sure normalization for display purposes work
    assert channel.to_simple_dict()["votes"] == 1.0

    # Make sure the rescale works for the channels
    metadata_store.Vsids[0].normalize()
    assert metadata_store.Vsids[0].bump_amount == 1.0
    assert channel.votes == 1.0

    # Ensure that vote by another person counts
    peer_key = default_eccrypto.generate_key("curve25519")
    metadata_store.vote_bump(channel.public_key, channel.id_, peer_key.pub().key_to_bin()[10:])
    assert channel.votes == 2.0

    freezer.move_to('2021-09-26')
    # Ensure that a repeated vote supersedes the first vote but does not count as a new one
    metadata_store.vote_bump(channel.public_key, channel.id_, peer_key.pub().key_to_bin()[10:])
    assert 2.0 < channel.votes < 2.5


@db_session
def test_commit_channel_torrent(metadata_store):
    """
    Test committing a channel torrent
    """
    channel = metadata_store.ChannelMetadata.create_channel('test', 'test')
    tdef = TorrentDef.load(TORRENT_UBUNTU_FILE)
    channel.add_torrent_to_channel(tdef, None)
    # The first run should return the infohash, the second should return None, because nothing was really done
    assert channel.commit_channel_torrent()
    assert not channel.commit_channel_torrent()

    # Test adding flags to channel torrent when adding thumbnail and description
    metadata_store.ChannelThumbnail(public_key=channel.public_key, origin_id=channel.id_, status=NEW)
    metadata_store.ChannelDescription(public_key=channel.public_key, origin_id=channel.id_, status=NEW)
    assert channel.commit_channel_torrent()
    assert channel.reserved_flags == 3
    assert not channel.commit_channel_torrent()


@pytest.mark.timeout(20)
@db_session
def test_recursive_commit_channel_torrent(metadata_store):
    status_types = [NEW, UPDATED, TODELETE, COMMITTED]

    def all_status_combinations():
        result = []
        for card in range(0, len(status_types) + 1):
            result.extend(list(combinations(status_types, card)))
        return result

    def generate_collection(parent, collection_status, contents_statuses, recurse=False):
        chan = metadata_store.CollectionNode(
            title=parent.title + '->child_new_nonempty', origin_id=parent.id_, status=collection_status
        )
        for s in contents_statuses:
            metadata_store.TorrentMetadata(infohash=random_infohash(), origin_id=chan.id_, status=s)
            if recurse:
                for status in status_types:
                    generate_collection(chan, status, [NEW])
        return chan

    def generate_channel(recurse=False, status=NEW):
        toplevel_channel = metadata_store.ChannelMetadata.create_channel('root', 'test')
        metadata_store.ChannelThumbnail(
            public_key=toplevel_channel.public_key,
            origin_id=toplevel_channel.id_,
            binary_data=os.urandom(20000),
            data_type="image/png",
        )
        metadata_store.ChannelDescription(
            public_key=toplevel_channel.public_key,
            origin_id=toplevel_channel.id_,
            json_text='{"description_text":"foobar"}',
        )
        toplevel_channel.status = status
        for s in status_types:
            metadata_store.TorrentMetadata(infohash=random_infohash(), origin_id=toplevel_channel.id_, status=s)
            if recurse:
                for status_combination in all_status_combinations():
                    generate_collection(toplevel_channel, s, status_combination, recurse=recurse)
        metadata_store.ChannelDescription(
            text="foobar",
            origin_id=toplevel_channel.id_,
        )
        return toplevel_channel

    # Make sure running commit on empty channels produces no error
    metadata_store.CollectionNode.commit_all_channels()

    # All types of non-empty and empty toplevel channels
    for s in status_types:
        empty_chan = metadata_store.ChannelMetadata.create_channel('root', 'test')
        empty_chan.status = s
        generate_channel(status=s)

    # A committed channel with a single deleted collection in it. It should not be deleted
    single_del_cont_chan = metadata_store.ChannelMetadata.create_channel('root', 'test')
    metadata_store.CollectionNode(status=TODELETE, origin_id=single_del_cont_chan.id_)

    # Create some orphaned MDs
    chan = generate_channel()
    orphaned_contents_rowids = [c.rowid for c in chan.get_contents_recursive()]
    metadata_store.ChannelNode.delete(chan)  # We use it to delete non-recursively

    # Create a top-level collection node
    coll = metadata_store.CollectionNode(origin_id=0, status=NEW)
    generate_collection(coll, NEW, [NEW, UPDATED, TODELETE])

    commit_results = metadata_store.CollectionNode.commit_all_channels()
    # Check that commit results in the correct number of torrents produced
    assert len(commit_results) == 4
    # Check that top-level collection node, while not committed to disk, still has its num_entries recalculated
    assert coll.num_entries == 2
    # Check that all orphaned entries are deleted during commit
    assert not metadata_store.ChannelNode.exists(lambda g: g.rowid in orphaned_contents_rowids)

    # Create a single nested channel
    chan = generate_channel(recurse=True)

    chan.commit_channel_torrent()
    chan.local_version = 0
    len(chan.get_contents_recursive())

    chan.consolidate_channel_torrent()
    # Remove the channel and read it back from disk
    for c in chan.contents:
        c.delete()
    my_dir = Path(metadata_store.ChannelMetadata._channels_dir / chan.dirname).absolute()
    metadata_store.process_channel_dir(my_dir, chan.public_key, chan.id_, skip_personal_metadata_payload=False)
    assert chan.num_entries == 366


@db_session
def test_consolidate_channel_torrent(torrent_template, metadata_store):
    """
    Test completely re-commit your channel
    """
    channel = metadata_store.ChannelMetadata.create_channel('test', 'test')
    my_dir = Path(metadata_store.ChannelMetadata._channels_dir / channel.dirname).absolute()
    tdef = TorrentDef.load(TORRENT_UBUNTU_FILE)

    # 1st torrent
    torrent_entry = channel.add_torrent_to_channel(tdef, None)
    channel.commit_channel_torrent()

    # 2nd torrent
    metadata_store.TorrentMetadata.from_dict(
        dict(torrent_template, public_key=channel.public_key, origin_id=channel.id_, status=NEW)
    )
    channel.commit_channel_torrent()
    # Delete entry
    torrent_entry.soft_delete()
    channel.commit_channel_torrent()

    assert len(channel.contents_list) == 1
    assert len(os.listdir(my_dir)) == 3

    torrent3 = metadata_store.TorrentMetadata(
        public_key=channel.public_key, origin_id=channel.id_, status=NEW, infohash=random_infohash()
    )
    channel.commit_channel_torrent()
    torrent3.soft_delete()

    channel.consolidate_channel_torrent()
    assert len(os.listdir(my_dir)) == 1
    metadata_store.TorrentMetadata.select(lambda g: g.metadata_type == REGULAR_TORRENT).delete()
    channel.local_version = 0
    metadata_store.process_channel_dir(my_dir, channel.public_key, channel.id_, skip_personal_metadata_payload=False)
    assert len(channel.contents[:]) == 1


@db_session
def test_data_dont_fit_in_mdblob(metadata_store):
    import random as rng  # pylint: disable=import-outside-toplevel

    rng.seed(123)
    md_list = [
        metadata_store.TorrentMetadata(
            title='test' + str(x),
            infohash=random_infohash(rng),
            id_=rng.randint(0, 100000000),
            torrent_date=int2time(rng.randint(0, 4000000)),
            timestamp=rng.randint(0, 100000000),
        )
        for x in range(0, 1)
    ]
    chunk, index = entries_to_chunk(md_list, chunk_size=1)
    assert index == 1
    assert len(chunk) == 205

    # Test corner case of empty list and/or too big index
    with pytest.raises(Exception):
        entries_to_chunk(md_list, chunk_size=1000, start_index=1000)
    with pytest.raises(Exception):
        entries_to_chunk([], chunk_size=1)


@db_session
def test_get_channels(metadata_store):
    """
    Test whether we can get channels
    """

    # First we create a few channels
    for ind in range(10):
        metadata_store.ChannelNode._my_key = default_eccrypto.generate_key('low')
        metadata_store.ChannelMetadata(title='channel%d' % ind, subscribed=(ind % 2 == 0), infohash=random_infohash())
        metadata_store.TorrentMetadata(title='tor%d' % ind, infohash=random_infohash())
    channels = metadata_store.get_entries(first=1, last=5, metadata_type=CHANNEL_TORRENT)
    assert len(channels) == 5

    # Test filtering
    channels = metadata_store.get_entries(first=1, last=5, metadata_type=CHANNEL_TORRENT, txt_filter='channel5')
    assert len(channels) == 1

    # Test sorting
    channels = metadata_store.get_entries(
        first=1, last=10, metadata_type=CHANNEL_TORRENT, sort_by='title', sort_desc=True
    )
    assert len(channels) == 10
    assert channels[0].title == 'channel9'

    # Test fetching subscribed channels
    channels = metadata_store.get_entries(
        first=1, last=10, metadata_type=CHANNEL_TORRENT, sort_by='title', subscribed=True
    )
    assert len(channels) == 5


@db_session
def test_default_sorting_no_fts(mds_with_some_torrents):
    metadata_store, channel = mds_with_some_torrents

    # Search through the entire set of torrents & folders.
    # Currently objects are returned in order "newest at first"
    objects = metadata_store.get_entries()
    titles = [obj.title.partition(' ')[0] for obj in objects]
    assert titles == [
        'torrent6',
        'torrent5',
        'channel2',
        'torrent2_1',
        'folder2_2',
        'folder2_1',
        'torrent4',
        'folder2',
        'torrent3',
        'torrent2',
        'folder1',
        'torrent1',
        'channel1',
    ]

    objects = metadata_store.get_entries(channel_pk=channel.public_key)
    titles = [obj.title.partition(' ')[0] for obj in objects]
    assert titles == [
        'torrent2_1',
        'folder2_2',
        'folder2_1',
        'torrent4',
        'folder2',
        'torrent3',
        'torrent2',
        'folder1',
        'torrent1',
        'channel1',
    ]

    objects = metadata_store.get_entries(origin_id=channel.id_)
    titles = [obj.title.partition(' ')[0] for obj in objects]
    assert titles == ['torrent4', 'folder2', 'torrent3', 'torrent2', 'folder1', 'torrent1']


@db_session
def test_default_sorting_with_fts(mds_with_some_torrents):
    metadata_store, channel = mds_with_some_torrents

    # Search through the entire set of torrents & folders.
    # Returns channels at first, then folders (newest at first),
    # then torrents (with seeders at first)
    objects = metadata_store.get_entries(txt_filter='aaa')
    titles = [obj.title.partition(' ')[0] for obj in objects]
    assert titles == [
        'channel2',
        'channel1',
        'folder2_1',
        'folder2',
        'folder1',
        'torrent2_1',  # has seeders
        'torrent1',  # has seeders
        'torrent5',  # has seeders
        'torrent6',  # no seeders
        'torrent2',  # no seeders
    ]

    objects = metadata_store.get_entries(channel_pk=channel.public_key, txt_filter='aaa')
    titles = [obj.title.partition(' ')[0] for obj in objects]
    assert titles == [
        'channel1',
        'folder2_1',
        'folder2',
        'folder1',
        'torrent2_1',  # has seeders
        'torrent1',  # has seeders
        'torrent2',  # no seeders
    ]

    objects = metadata_store.get_entries(origin_id=channel.id_, txt_filter='aaa')
    titles = [obj.title.partition(' ')[0] for obj in objects]
    assert titles == ['folder2', 'folder1', 'torrent1', 'torrent2']


@db_session
def test_sort_by_health_no_fts(mds_with_some_torrents):
    metadata_store, channel = mds_with_some_torrents

    objects = metadata_store.get_entries(sort_by='HEALTH', sort_desc=True)
    titles = [obj.title.partition(' ')[0] for obj in objects]
    assert titles == [
        'torrent4',  # 30 seeders
        'torrent2_1',  # 20 seeders
        'torrent1',  # 10 seeders
        'torrent3',  # 5 seeders
        'torrent5',  # 1 seeders
        'torrent6',  # no seeders
        'channel2',
        'torrent2',  # no seeders
        'channel1',
        'folder2_2',
        'folder2_1',
        'folder2',
        'folder1',
    ]

    objects = metadata_store.get_entries(sort_by='HEALTH', sort_desc=False)
    titles = [obj.title.partition(' ')[0] for obj in objects]
    assert titles == [
        'folder1',
        'folder2',
        'folder2_1',
        'folder2_2',
        'channel1',
        'torrent2',  # no seeders
        'channel2',
        'torrent6',  # no seeders
        'torrent5',  # 1 seeders
        'torrent3',  # 2 seeders
        'torrent1',  # 10 seeders
        'torrent2_1',  # 20 seeders
        'torrent4',  # 30 seeders
    ]

    objects = metadata_store.get_entries(channel_pk=channel.public_key, sort_by='HEALTH', sort_desc=True)
    titles = [obj.title.partition(' ')[0] for obj in objects]
    assert titles == [
        'torrent4',  # has seeders
        'torrent2_1',  # has seeders
        'torrent1',  # has seeders
        'torrent3',  # has seeders
        'torrent2',  # no seeders
        'channel1',
        'folder2_2',
        'folder2_1',
        'folder2',
        'folder1',
    ]

    objects = metadata_store.get_entries(channel_pk=channel.public_key, sort_by='HEALTH', sort_desc=False)
    titles = [obj.title.partition(' ')[0] for obj in objects]
    assert titles == [
        'folder1',
        'folder2',
        'folder2_1',
        'folder2_2',
        'channel1',
        'torrent2',  # no seeders
        'torrent3',  # has seeders
        'torrent1',  # has seeders
        'torrent2_1',  # has seeders
        'torrent4',  # has seeders
    ]

    objects = metadata_store.get_entries(
        origin_id=channel.id_,
        sort_by='HEALTH',
        sort_desc=True,
    )
    titles = [obj.title.partition(' ')[0] for obj in objects]
    assert titles == [
        'torrent4',  # has seeders
        'torrent1',  # has seeders
        'torrent3',  # has seeders
        'torrent2',  # no seeders
        'folder2',
        'folder1',
    ]

    objects = metadata_store.get_entries(origin_id=channel.id_, sort_by='HEALTH', sort_desc=False)
    titles = [obj.title.partition(' ')[0] for obj in objects]
    assert titles == [
        'folder1',
        'folder2',
        'torrent2',  # no seeders
        'torrent3',  # has seeders
        'torrent1',  # has seeders
        'torrent4',  # has seeders
    ]


@db_session
def test_sort_by_health_with_fts(mds_with_some_torrents):
    metadata_store, channel = mds_with_some_torrents

    objects = metadata_store.get_entries(txt_filter='aaa', sort_by='HEALTH', sort_desc=True)
    titles = [obj.title.partition(' ')[0] for obj in objects]
    assert titles == [
        'torrent2_1',  # 20 seeders
        'torrent1',  # 10 seeders
        'torrent5',  # 1 seeder
        'torrent6',  # no seeders
        'channel2',
        'torrent2',
        'channel1',
        'folder2_1',
        'folder2',
        'folder1',
    ]

    objects = metadata_store.get_entries(txt_filter='aaa', sort_by='HEALTH', sort_desc=False)
    titles = [obj.title.partition(' ')[0] for obj in objects]
    assert titles == [
        'folder1',
        'folder2',
        'folder2_1',
        'channel1',
        'torrent2',
        'channel2',
        'torrent6',  # no seeders
        'torrent5',  # 1 seeder
        'torrent1',  # 10 seeders
        'torrent2_1',  # 20 seeders
    ]

    objects = metadata_store.get_entries(
        channel_pk=channel.public_key, txt_filter='aaa', sort_by='HEALTH', sort_desc=True
    )
    titles = [obj.title.partition(' ')[0] for obj in objects]
    assert titles == [
        'torrent2_1',  # 20 seeders
        'torrent1',  # 10 seeders
        'torrent2',  # no seeders
        'channel1',
        'folder2_1',
        'folder2',
        'folder1',
    ]

    objects = metadata_store.get_entries(
        channel_pk=channel.public_key, txt_filter='aaa', sort_by='HEALTH', sort_desc=False
    )
    titles = [obj.title.partition(' ')[0] for obj in objects]
    assert titles == [
        'folder1',
        'folder2',
        'folder2_1',
        'channel1',
        'torrent2',  # no seeders
        'torrent1',  # 10 seeders
        'torrent2_1',  # 20 seeders
    ]

    objects = metadata_store.get_entries(
        origin_id=channel.id_,
        txt_filter='aaa',
        sort_by='HEALTH',
        sort_desc=True,
    )
    titles = [obj.title.partition(' ')[0] for obj in objects]
    assert titles == ['torrent1', 'torrent2', 'folder2', 'folder1']

    objects = metadata_store.get_entries(origin_id=channel.id_, txt_filter='aaa', sort_by='HEALTH', sort_desc=False)
    titles = [obj.title.partition(' ')[0] for obj in objects]
    assert titles == ['folder1', 'folder2', 'torrent2', 'torrent1']


@db_session
def test_get_channel_name(metadata_store):
    """
    Test getting torrent name for a channel to be displayed in the downloads list
    """
    infohash = b"\x00" * 20
    title = "testchan"
    chan = metadata_store.ChannelMetadata(title=title, infohash=infohash)
    dirname = chan.dirname

    assert title == metadata_store.ChannelMetadata.get_channel_name(dirname, infohash)
    assert title == metadata_store.ChannelMetadata.get_channel_name_cached(dirname, infohash)
    chan.infohash = b"\x11" * 20
    assert "OLD:" + title == metadata_store.ChannelMetadata.get_channel_name(dirname, infohash)
    chan.delete()
    assert dirname == metadata_store.ChannelMetadata.get_channel_name(dirname, infohash)
    # Check that the cached version of the name is returned even if the channel has been deleted
    metadata_store.ChannelMetadata.get_channel_name = Mock()
    assert title == metadata_store.ChannelMetadata.get_channel_name_cached(dirname, infohash)
    metadata_store.ChannelMetadata.get_channel_name.assert_not_called()


@db_session
def check_add(metadata_store, torrents_in_dir, errors, recursive):
    TEST_TORRENTS_DIR = TESTS_DATA_DIR / 'linux_torrents'
    chan = metadata_store.ChannelMetadata.create_channel(title='testchan')
    torrents, e = chan.add_torrents_from_dir(TEST_TORRENTS_DIR, recursive)
    assert torrents_in_dir == len(torrents)
    assert errors == len(e)
    with db_session:
        q = metadata_store.TorrentMetadata.select(lambda g: g.metadata_type == REGULAR_TORRENT)
        assert torrents_in_dir - len(e) == q.count()


def test_add_torrents_from_dir(metadata_store):
    check_add(metadata_store, 9, 0, recursive=False)


def test_add_torrents_from_dir_recursive(metadata_store):
    check_add(metadata_store, 11, 1, recursive=True)


@db_session
def create_ext_chan(metadata_store, ext_key):
    src_chan = metadata_store.ChannelMetadata(sign_with=ext_key, title="bla", infohash=random_infohash())
    metadata_store.TorrentMetadata(origin_id=src_chan.id_, sign_with=ext_key, infohash=random_infohash())
    l2_coll1 = metadata_store.CollectionNode(origin_id=src_chan.id_, sign_with=ext_key, title="bla-l2-1")
    metadata_store.TorrentMetadata(origin_id=l2_coll1.id_, sign_with=ext_key, infohash=random_infohash())
    metadata_store.TorrentMetadata(origin_id=l2_coll1.id_, sign_with=ext_key, infohash=random_infohash())
    l2_coll2 = metadata_store.CollectionNode(origin_id=src_chan.id_, sign_with=ext_key, title="bla-l2-2")
    metadata_store.TorrentMetadata(origin_id=l2_coll2.id_, sign_with=ext_key, infohash=random_infohash())
    metadata_store.TorrentMetadata(origin_id=l2_coll2.id_, sign_with=ext_key, infohash=random_infohash())
    return src_chan


@db_session
def test_make_copy(metadata_store):
    """
    Test copying if recursive copying an external channel to a personal channel works as expected
    """
    src_chan = create_ext_chan(metadata_store, default_eccrypto.generate_key("curve25519"))

    tgt_chan = metadata_store.ChannelMetadata(title='our chan', infohash=random_infohash(), status=NEW)
    src_chan.make_copy(tgt_chan.id_)
    src_chan.pprint_tree()
    tgt_chan.pprint_tree()
    copy = metadata_store.CollectionNode.get(public_key=tgt_chan.public_key, origin_id=tgt_chan.id_)
    assert copy.title == "bla"
    assert 1 + len(src_chan.get_contents_recursive()) == len(tgt_chan.get_contents_recursive())


@db_session
def test_update_properties_move(metadata_store):
    """
    Test moving a Channel/Collection into another Channel/Collection or at the top of channel hierachy.
    """
    src_chan = create_ext_chan(metadata_store, metadata_store.ChannelMetadata._my_key)
    src_chan_contents = src_chan.get_contents_recursive()
    tgt_chan = metadata_store.ChannelMetadata.create_channel('dstchan')

    # Move channel into another channel so it becomes a collection
    result_chan = src_chan.update_properties({'origin_id': tgt_chan.id_})
    # Assert the moved channel changed type to collection
    assert isinstance(result_chan, metadata_store.CollectionNode)
    assert result_chan.metadata_type == COLLECTION_NODE
    assert 1 + len(src_chan_contents) == len(tgt_chan.get_contents_recursive())

    # Move collection to top level so it become a channel
    result_chan = result_chan.update_properties({'origin_id': 0})
    # Assert the move collection changed type to channel
    assert isinstance(result_chan, metadata_store.ChannelMetadata)
    assert result_chan.metadata_type == CHANNEL_TORRENT


@db_session
def test_delete_recursive(metadata_store):
    """
    Test deleting channel and its contents recursively
    """
    src_chan = create_ext_chan(metadata_store, default_eccrypto.generate_key("curve25519"))
    src_chan.delete()
    assert not metadata_store.ChannelNode.select().count()

    src_chan = create_ext_chan(metadata_store, default_eccrypto.generate_key("curve25519"))
    src_chan_rowid = src_chan.rowid
    src_chan.delete(recursive=False)
    assert metadata_store.ChannelNode.select().count() == 7
    with pytest.raises(ObjectNotFound):
        metadata_store.ChannelNode.__getitem__(src_chan_rowid)


@db_session
def test_get_parents(metadata_store):
    """
    Test the routine that gets the full set (path) of a node's predecessors in the channels tree
    """
    key = default_eccrypto.generate_key("curve25519")
    src_chan = create_ext_chan(metadata_store, key)
    coll1 = metadata_store.CollectionNode.select(lambda g: g.origin_id == src_chan.id_).first()
    torr1 = coll1.contents.first()
    assert (src_chan, coll1, torr1) == torr1.get_parent_nodes()

    loop = metadata_store.CollectionNode(id_=777, origin_id=777)
    assert loop.get_parent_nodes() == (loop,)


@db_session
def test_collection_node_state(metadata_store):
    """
    Test that CollectionNode state is inherited from the top-level parent channel
    """
    key = default_eccrypto.generate_key("curve25519")
    src_chan = create_ext_chan(metadata_store, key)
    coll1 = metadata_store.CollectionNode.select(lambda g: g.origin_id == src_chan.id_).first()

    # Initially, the top level parent channel is in the preview state, so must be the collection
    assert coll1.state == CHANNEL_STATE.PREVIEW.value

    src_chan.local_version = src_chan.timestamp
    # Now the top level parent channel is complete, so must become the collection
    assert coll1.state == CHANNEL_STATE.COMPLETE.value

    # For personal collections, state should always be "personal" no matter what
    pers_chan = metadata_store.ChannelMetadata(infohash=random_infohash())
    pers_coll = metadata_store.CollectionNode(origin_id=pers_chan.id_)
    assert pers_coll.state == CHANNEL_STATE.PERSONAL.value


@db_session
def test_metadata_compressor():
    SERIALIZED_METADATA = f"<{'S' * 1000}>".encode('ascii')
    SERIALIZED_DELETE = f"<{'D' * 100}>".encode('ascii')
    SERIALIZED_HEALTH = "1,2,1234567890;".encode('ascii')

    metadata = Mock()
    metadata.status = NEW
    metadata.serialized = Mock(return_value=SERIALIZED_METADATA)
    metadata.serialized_delete = Mock(return_value=SERIALIZED_DELETE)
    metadata.serialized_health = Mock(return_value=SERIALIZED_HEALTH)

    def add_items(mc: MetadataCompressor, expected_items_count: int):
        prev_size = 0
        for i in range(1, 1000):
            item_was_added = mc.put(metadata)
            if not item_was_added:
                assert mc.count == i - 1  # last item was not added
                assert mc.count == expected_items_count  # compressor was able to add 10 items only
                break

            assert mc.count == i  # after the element was successfully added, the count should increase
            assert mc.size > prev_size  # with each item the total size should become bigger
            prev_size = mc.size
        else:
            assert False  # too many items was added, something is wrong

        assert prev_size < mc.chunk_size  # total size should fit into the chunk

        assert not mc.closed
        result = mc.close()
        assert mc.closed
        assert isinstance(result, bytes)
        assert len(result) == prev_size
        assert len(result) < len(SERIALIZED_METADATA) * expected_items_count  # our test data should be easy to compress

        return result

    # compressing a normal data without a health info

    mc = MetadataCompressor(200)
    assert mc.chunk_size == 200
    assert not mc.include_health  # include_health is False by default
    assert mc.count == 0  # no items added yet

    expected_items_count = 10  # chunk of size 200 should be enough to put 10 test items
    data = add_items(mc, expected_items_count)

    d = LZ4FrameDecompressor()
    decompressed = d.decompress(data)
    assert decompressed == SERIALIZED_METADATA * expected_items_count  # check the correctness of the decompressed data
    unused_data = d.unused_data
    assert not unused_data  # if health info is not included, no unused_data should be placed after the LZ4 frame

    assert metadata.serialized_health.assert_not_called
    assert metadata.serialized_delete.assert_not_called

    # cannot operate on closed MetadataCompressor

    with pytest.raises(TypeError, match='^Compressor is already closed$'):
        mc.put(metadata)

    with pytest.raises(TypeError, match='^Compressor is already closed$'):
        mc.close()

    # chunk size is not enough even for a single item

    mc = MetadataCompressor(10)
    added = mc.put(metadata)
    # first item should be added successfully even if the size of compressed item is bigger than the chunk size
    assert added
    size = mc.size
    assert size > mc.chunk_size

    added = mc.put(metadata)
    assert not added  # second item was not added
    assert mc.count == 1
    assert mc.size == size  # size was not changed

    data = mc.close()
    d = LZ4FrameDecompressor()
    decompressed = d.decompress(data)
    assert decompressed == SERIALIZED_METADATA

    # include health info

    mc = MetadataCompressor(200, True)
    assert mc.include_health

    expected_items_count = 5  # with health info we can put at most 10 test items into the chunk of size 200
    data = add_items(mc, expected_items_count)

    d = LZ4FrameDecompressor()
    decompressed = d.decompress(data)
    assert decompressed == SERIALIZED_METADATA * expected_items_count  # check the correctness of the decompressed data
    unused_data = d.unused_data

    assert metadata.serialized_health.assert_called
    assert metadata.serialized_delete.assert_not_called

    health_items = HealthItemsPayload.unpack(unused_data)
    assert len(health_items) == expected_items_count
    for health_item in health_items:
        assert health_item == (1, 2, 1234567890)


def test_unpack_health_items():
    data = HealthItemsPayload(b';;1,2,3;;4,5,6,foo,bar;7,8,9,baz;;ignored data').serialize()
    items = HealthItemsPayload.unpack(data)
    assert items == [
        (0, 0, 0),
        (0, 0, 0),
        (1, 2, 3),
        (0, 0, 0),
        (4, 5, 6),
        (7, 8, 9),
        (0, 0, 0),
    ]


def test_parse_health_data_item():
    item = HealthItemsPayload.parse_health_data_item(b'')
    assert item == (0, 0, 0)

    item = HealthItemsPayload.parse_health_data_item(b'invalid item')
    assert item == (0, 0, 0)

    item = HealthItemsPayload.parse_health_data_item(b'1,2,3')
    assert item == (1, 2, 3)

    item = HealthItemsPayload.parse_health_data_item(b'-1,2,3')
    assert item == (0, 0, 0)

    item = HealthItemsPayload.parse_health_data_item(b'1,-2,3')
    assert item == (0, 0, 0)

    item = HealthItemsPayload.parse_health_data_item(b'1,2,-3')
    assert item == (0, 0, 0)

    item = HealthItemsPayload.parse_health_data_item(b'100,200,300')
    assert item == (100, 200, 300)

    item = HealthItemsPayload.parse_health_data_item(b'2,3,4,5,6,7')
    assert item == (2, 3, 4)

    item = HealthItemsPayload.parse_health_data_item(b'3,4,5,some arbitrary,data,foo,,bar')
    assert item == (3, 4, 5)
