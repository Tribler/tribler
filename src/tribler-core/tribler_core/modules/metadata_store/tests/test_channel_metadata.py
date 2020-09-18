import os
from binascii import unhexlify
from datetime import datetime
from itertools import combinations
from time import sleep
from unittest.mock import Mock, patch

from ipv8.database import database_blob
from ipv8.keyvault.crypto import default_eccrypto

from pony.orm import ObjectNotFound, db_session

import pytest

from tribler_core.exceptions import DuplicateTorrentFileError
from tribler_core.modules.libtorrent.torrentdef import TorrentDef
from tribler_core.modules.metadata_store.orm_bindings.channel_metadata import CHANNEL_DIR_NAME_LENGTH, entries_to_chunk
from tribler_core.modules.metadata_store.orm_bindings.channel_node import COMMITTED, NEW, TODELETE, UPDATED
from tribler_core.modules.metadata_store.serialization import CHANNEL_TORRENT, COLLECTION_NODE, REGULAR_TORRENT
from tribler_core.tests.tools.common import TESTS_DATA_DIR, TORRENT_UBUNTU_FILE
from tribler_core.utilities import path_util
from tribler_core.utilities.random_utils import random_infohash


@pytest.fixture
def my_key():
    return default_eccrypto.generate_key(u"curve25519")


@pytest.fixture
def torrent_template():
    return {"title": "", "infohash": b"", "torrent_date": datetime(1970, 1, 1), "tags": "video"}


@pytest.fixture
def sample_torrent_dict(my_key):
    return {
        "infohash": database_blob(b"1" * 20),
        "size": 123,
        "torrent_date": datetime.utcnow(),
        "tags": "bla",
        "id_": 123,
        "public_key": database_blob(my_key.pub().key_to_bin()[10:]),
        "title": "lalala",
    }


@pytest.fixture
def sample_channel_dict(sample_torrent_dict):
    return dict(sample_torrent_dict, votes=222, subscribed=False, timestamp=1)


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
    channel_metadata.public_key = database_blob(unhexlify('0' * 128))
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
    with pytest.raises(DuplicateTorrentFileError):
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
    new_tracker_address = u'http://tribler.org/announce'
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


@db_session
def test_vsids(metadata_store):
    """
    Test VSIDS-based channel popularity system.
    """
    peer_key = default_eccrypto.generate_key(u"curve25519")
    assert metadata_store.Vsids[0].bump_amount == 1.0

    channel = metadata_store.ChannelMetadata.create_channel('test', 'test')
    metadata_store.vote_bump(channel.public_key, channel.id_, peer_key.pub().key_to_bin()[10:])
    sleep(0.1)  # Necessary mostly on Windows, because of the lower timer resolution
    metadata_store.vote_bump(channel.public_key, channel.id_, peer_key.pub().key_to_bin()[10:])
    assert channel.votes > 0.0
    assert metadata_store.Vsids[0].bump_amount > 1.0

    # Make sure normalization for display purposes work
    assert channel.to_simple_dict()["votes"] == 1.0

    # Make sure the rescale works for the channels
    metadata_store.Vsids[0].normalize()
    assert metadata_store.Vsids[0].bump_amount == 1.0
    assert channel.votes == 1.0


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


@pytest.mark.timeout(10)
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
        toplevel_channel.status = status
        for s in status_types:
            metadata_store.TorrentMetadata(infohash=random_infohash(), origin_id=toplevel_channel.id_, status=s)
            if recurse:
                for status_combination in all_status_combinations():
                    generate_collection(toplevel_channel, s, status_combination, recurse=recurse)
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
    my_dir = path_util.abspath(metadata_store.ChannelMetadata._channels_dir / chan.dirname)
    metadata_store.process_channel_dir(my_dir, chan.public_key, chan.id_, skip_personal_metadata_payload=False)
    assert chan.num_entries == 363


@db_session
def test_consolidate_channel_torrent(torrent_template, metadata_store):
    """
    Test completely re-commit your channel
    """
    channel = metadata_store.ChannelMetadata.create_channel('test', 'test')
    my_dir = path_util.abspath(metadata_store.ChannelMetadata._channels_dir / channel.dirname)
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
def test_mdblob_dont_fit_exception(metadata_store):
    with pytest.raises(Exception):
        md_list = [
            metadata_store.TorrentMetadata(title='test' + str(x), infohash=random_infohash()) for x in range(0, 1)
        ]
        entries_to_chunk(md_list, chunk_size=1)


@db_session
def test_get_channels(metadata_store):
    """
    Test whether we can get channels
    """

    # First we create a few channels
    for ind in range(10):
        metadata_store.ChannelNode._my_key = default_eccrypto.generate_key('low')
        metadata_store.ChannelMetadata(title='channel%d' % ind, subscribed=(ind % 2 == 0), infohash=random_infohash())
    channels = metadata_store.ChannelMetadata.get_entries(first=1, last=5)
    assert len(channels) == 5

    # Test filtering
    channels = metadata_store.ChannelMetadata.get_entries(first=1, last=5, txt_filter='channel5')
    assert len(channels) == 1

    # Test sorting
    channels = metadata_store.ChannelMetadata.get_entries(first=1, last=10, sort_by='title', sort_desc=True)
    assert len(channels) == 10
    assert channels[0].title == 'channel9'

    # Test fetching subscribed channels
    channels = metadata_store.ChannelMetadata.get_entries(first=1, last=10, sort_by='title', subscribed=True)
    assert len(channels) == 5


@db_session
def test_get_channel_name(metadata_store):
    """
    Test getting torrent name for a channel to be displayed in the downloads list
    """
    infohash = b"\x00" * 20
    title = "testchan"
    chan = metadata_store.ChannelMetadata(title=title, infohash=database_blob(infohash))
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
    src_chan = create_ext_chan(metadata_store, default_eccrypto.generate_key(u"curve25519"))

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
    src_chan = create_ext_chan(metadata_store, default_eccrypto.generate_key(u"curve25519"))
    src_chan.delete()
    assert not metadata_store.ChannelNode.select().count()

    src_chan = create_ext_chan(metadata_store, default_eccrypto.generate_key(u"curve25519"))
    src_chan_rowid = src_chan.rowid
    src_chan.delete(recursive=False)
    assert metadata_store.ChannelNode.select().count() == 7
    with pytest.raises(ObjectNotFound):
        metadata_store.ChannelNode.__getitem__(src_chan_rowid)


@db_session
def test_get_parent_ids(metadata_store):
    """
    Test the routine that gets the full set (path) of a node's predecessors in the channels tree
    """
    src_chan = create_ext_chan(metadata_store, default_eccrypto.generate_key(u"curve25519"))
    coll1 = metadata_store.CollectionNode.select(lambda g: g.origin_id == src_chan.id_).first()
    assert (0, src_chan.id_, coll1.id_) == coll1.contents.first().get_parents_ids()

    loop = metadata_store.CollectionNode(id_=777, origin_id=777)
    assert 0 not in loop.get_parents_ids()
