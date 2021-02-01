import os
import random
import string
from binascii import unhexlify
from datetime import datetime
from pathlib import Path
from unittest.mock import patch

from ipv8.database import database_blob
from ipv8.keyvault.crypto import default_eccrypto

from pony.orm import db_session

import pytest

from tribler_core.modules.metadata_store.orm_bindings.channel_metadata import CHANNEL_DIR_NAME_LENGTH, entries_to_chunk
from tribler_core.modules.metadata_store.orm_bindings.channel_node import NEW
from tribler_core.modules.metadata_store.serialization import (
    CHANNEL_TORRENT,
    ChannelMetadataPayload,
    DeletedMetadataPayload,
    SignedPayload,
    UnknownBlobTypeException,
)
from tribler_core.modules.metadata_store.store import (
    DELETED_METADATA,
    GOT_NEWER_VERSION,
    NO_ACTION,
    UNKNOWN_CHANNEL,
    UNKNOWN_COLLECTION,
    UNKNOWN_TORRENT,
)
from tribler_core.modules.metadata_store.tests.test_channel_download import CHANNEL_METADATA_UPDATED
from tribler_core.tests.tools.common import TESTS_DATA_DIR
from tribler_core.utilities.path_util import str_path
from tribler_core.utilities.random_utils import random_infohash


def get_payloads(entity_class):
    c = entity_class(infohash=database_blob(random_infohash()))
    payload = c._payload_class.from_signed_blob(c.serialized())
    deleted_payload = DeletedMetadataPayload.from_signed_blob(c.serialized_delete())
    return c, payload, deleted_payload


def make_wrong_payload(filename):
    key = default_eccrypto.generate_key("curve25519")
    metadata_payload = SignedPayload(
        666, 0, database_blob(key.pub().key_to_bin()[10:]), signature=b'\x00' * 64, skip_key_check=True
    )
    with open(filename, 'wb') as output_file:
        output_file.write(metadata_payload.serialized())


SAMPLE_DIR = TESTS_DATA_DIR / 'sample_channel'
# Just get the first and only subdir there, and assume it is the sample channel dir
CHANNEL_DIR = [
    SAMPLE_DIR / subdir
    for subdir in os.listdir(SAMPLE_DIR)
    if (SAMPLE_DIR / subdir).is_dir() and len(subdir) == CHANNEL_DIR_NAME_LENGTH
][0]
CHANNEL_METADATA = TESTS_DATA_DIR / 'sample_channel' / 'channel.mdblob'


@db_session
def test_process_channel_dir_file(tmpdir, metadata_store):
    """
    Test whether we are able to process files in a directory containing node metadata
    """
    test_node_metadata = metadata_store.TorrentMetadata(title='test', infohash=database_blob(random_infohash()))
    metadata_path = tmpdir / 'metadata.data'
    test_node_metadata.to_file(metadata_path)
    # We delete this TorrentMeta info now, it should be added again to the database when loading it
    test_node_metadata.delete()
    loaded_metadata = metadata_store.process_mdblob_file(metadata_path, skip_personal_metadata_payload=False)
    assert loaded_metadata[0][0].title == 'test'

    # Test whether we delete existing metadata when loading a DeletedMetadata blob
    metadata = metadata_store.TorrentMetadata(infohash=b'1' * 20)
    metadata.to_delete_file(metadata_path)
    loaded_metadata = metadata_store.process_mdblob_file(metadata_path, skip_personal_metadata_payload=False)
    # Make sure the original metadata is deleted
    assert loaded_metadata[0] == (None, 6)
    assert metadata_store.TorrentMetadata.get(infohash=b'1' * 20) is None

    # Test an unknown metadata type, this should raise an exception
    invalid_metadata = tmpdir / 'invalidtype.mdblob'
    make_wrong_payload(invalid_metadata)
    with pytest.raises(UnknownBlobTypeException):
        metadata_store.process_mdblob_file(invalid_metadata, skip_personal_metadata_payload=False)


@pytest.mark.skip(reason="This test is currently unstable")
@db_session
def test_squash_mdblobs(metadata_store):
    chunk_size = metadata_store.ChannelMetadata._CHUNK_SIZE_LIMIT
    md_list = [
        metadata_store.TorrentMetadata(
            title=''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(20)),
            infohash=database_blob(random_infohash()),
            torrent_date=datetime.utcfromtimestamp(100),
        )
        for _ in range(0, 10)
    ]
    chunk, _ = entries_to_chunk(md_list, chunk_size=chunk_size)
    dict_list = [d.to_dict()["signature"] for d in md_list]
    for d in md_list:
        d.delete()
    assert dict_list == [
        d[0].to_dict()["signature"]
        for d in metadata_store.process_compressed_mdblob(chunk, skip_personal_metadata_payload=False)
    ]


@pytest.mark.skip(reason="This test is currently unstable")
@db_session
def test_squash_mdblobs_multiple_chunks(metadata_store):
    md_list = [
        metadata_store.TorrentMetadata(
            title=''.join(random.choice(string.ascii_uppercase + string.digits) for _ in range(20)),
            infohash=database_blob(random_infohash()),
            torrent_date=datetime.utcfromtimestamp(100),
        )
        for _ in range(0, 10)
    ]
    # Test splitting into multiple chunks
    chunk, index = entries_to_chunk(md_list, chunk_size=900)
    chunk2, _ = entries_to_chunk(md_list, chunk_size=900, start_index=index)
    dict_list = [d.to_dict()["signature"] for d in md_list]
    for d in md_list:
        d.delete()
    assert dict_list[:index] == [
        d[0].to_dict()["signature"]
        for d in metadata_store.process_compressed_mdblob(chunk, skip_personal_metadata_payload=False)
    ]

    assert dict_list[index:] == [
        d[0].to_dict()["signature"]
        for d in metadata_store.process_compressed_mdblob(chunk2, skip_personal_metadata_payload=False)
    ]


@db_session
def test_multiple_squashed_commit_and_read(metadata_store):
    """
    Test committing entries into several squashed blobs and reading them back
    """
    metadata_store.ChannelMetadata._CHUNK_SIZE_LIMIT = 500

    num_entries = 10
    channel = metadata_store.ChannelMetadata.create_channel('testchan')
    md_list = [
        metadata_store.TorrentMetadata(
            origin_id=channel.id_, title='test' + str(x), status=NEW, infohash=database_blob(random_infohash())
        )
        for x in range(0, num_entries)
    ]
    channel.commit_channel_torrent()

    channel.local_version = 0
    for md in md_list:
        md.delete()

    channel_dir = Path(metadata_store.ChannelMetadata._channels_dir) / channel.dirname
    assert len(os.listdir(channel_dir)) > 1  # make sure it was broken into more than one .mdblob file
    metadata_store.process_channel_dir(
        channel_dir, channel.public_key, channel.id_, skip_personal_metadata_payload=False
    )
    assert num_entries == len(channel.contents)


@db_session
def test_skip_processing_of_received_personal_channel_torrents(metadata_store):
    """
    Test that personal torrent is ignored by default when processing the torrent metadata payload
    """
    channel = metadata_store.ChannelMetadata.create_channel('testchan')
    torrent_md = metadata_store.TorrentMetadata(
        origin_id=channel.id_, title='test', status=NEW, infohash=database_blob(random_infohash())
    )
    channel.commit_channel_torrent()
    torrent_md.delete()

    channel_dir = Path(metadata_store.ChannelMetadata._channels_dir) / channel.dirname
    assert os.listdir(str_path(channel_dir))

    # By default, personal channel torrent metadata processing is skipped so there should be no torrents
    # added to the channel
    channel.local_version = 0
    metadata_store.process_channel_dir(channel_dir, channel.public_key, channel.id_)
    assert not channel.contents

    # Enable processing of personal channel torrent metadata
    channel.local_version = 0
    metadata_store.process_channel_dir(
        channel_dir, channel.public_key, channel.id_, skip_personal_metadata_payload=False
    )
    assert len(channel.contents) == 1


@db_session
def test_skip_processing_mdblob_with_forbidden_terms(metadata_store):
    """
    Test that an mdblob with forbidden terms cannot ever get into the local database
    """
    key = default_eccrypto.generate_key("curve25519")
    chan_entry = metadata_store.ChannelMetadata(title="12yo", infohash=database_blob(random_infohash()), sign_with=key)
    chan_payload = chan_entry._payload_class(**chan_entry.to_dict())
    chan_entry.delete()
    assert metadata_store.process_payload(chan_payload) == [(None, NO_ACTION)]


@db_session
def test_process_invalid_compressed_mdblob(metadata_store):
    """
    Test whether processing an invalid compressed mdblob does not crash Tribler
    """
    assert not metadata_store.process_compressed_mdblob(b"abcdefg")


@db_session
def test_process_channel_dir(metadata_store):
    """
    Test processing a directory containing metadata blobs
    """
    payload = ChannelMetadataPayload.from_file(CHANNEL_METADATA)
    channel = metadata_store.process_payload(payload)[0][0]
    assert not channel.contents_list
    metadata_store.process_channel_dir(CHANNEL_DIR, channel.public_key, channel.id_)
    assert len(channel.contents_list) == 4
    assert channel.timestamp == 1565621688015
    assert channel.local_version == channel.timestamp


@db_session
def test_compute_channel_update_progress(metadata_store, tmpdir):
    """
    Test estimating progress of channel processing
    """
    payload = ChannelMetadataPayload.from_file(CHANNEL_METADATA_UPDATED)
    channel = metadata_store.process_payload(payload)[0][0]
    with patch.object(metadata_store, 'get_channel_dir_path', lambda _: Path(CHANNEL_DIR)):
        assert metadata_store.compute_channel_update_progress(channel) == 0.0
        metadata_store.process_channel_dir(CHANNEL_DIR, channel.public_key, channel.id_)
        assert metadata_store.compute_channel_update_progress(channel) == 1.0


@db_session
def test_process_payload(metadata_store):

    metadata_store.ChannelNode._my_key = default_eccrypto.generate_key("curve25519")
    _, node_payload, node_deleted_payload = get_payloads(metadata_store.ChannelNode)

    assert not metadata_store.process_payload(node_payload)
    assert [(None, DELETED_METADATA)] == metadata_store.process_payload(node_deleted_payload)
    # Do nothing in case it is unknown/abstract payload type, like ChannelNode
    assert not metadata_store.process_payload(node_payload)

    for md_class, expected_reaction in (
        (metadata_store.ChannelMetadata, UNKNOWN_CHANNEL),
        (metadata_store.TorrentMetadata, UNKNOWN_TORRENT),
        (metadata_store.CollectionNode, UNKNOWN_COLLECTION),
    ):
        node, node_payload, node_deleted_payload = get_payloads(md_class)
        node_dict = node.to_dict()
        node.delete()

        # Check that there is no action if trying to delete an unknown object
        assert not metadata_store.process_payload(node_deleted_payload)

        # Check if node metadata object is properly created on payload processing
        processed_node, reaction = metadata_store.process_payload(node_payload)[0]
        assert reaction == expected_reaction
        assert node_dict['metadata_type'] == processed_node.to_dict()['metadata_type']

        # Check that payload processing returns the local node in case we already now about it
        assert processed_node, NO_ACTION == metadata_store.process_payload(node_payload)[0]


@db_session
def test_process_payload_ffa(metadata_store):
    infohash = b"1" * 20
    ffa_torrent = metadata_store.TorrentMetadata.add_ffa_from_dict(dict(infohash=infohash, title='abc'))
    ffa_payload = metadata_store.TorrentMetadata._payload_class.from_signed_blob(ffa_torrent.serialized())
    ffa_torrent.delete()

    # Assert that FFA is never added to DB if there is already a signed entry with the same infohash
    signed_md = metadata_store.TorrentMetadata(infohash=infohash, title="sdfsdfsdf")
    metadata_store.TorrentMetadata._payload_class.from_signed_blob(signed_md.serialized())
    assert [(None, NO_ACTION)] == metadata_store.process_payload(ffa_payload)
    signed_md.delete()

    # Add an FFA from the payload
    md, result = metadata_store.process_payload(ffa_payload)[0]
    assert UNKNOWN_TORRENT == result
    assert md

    # Assert that older FFAs are never replaced by newer ones with the same infohash
    assert [(None, NO_ACTION)] == metadata_store.process_payload(ffa_payload)


@db_session
def test_get_parents_ids(metadata_store):
    channel = metadata_store.ChannelMetadata(infohash=database_blob(random_infohash()))
    folder = metadata_store.CollectionNode(origin_id=channel.id_)
    torrent = metadata_store.TorrentMetadata(origin_id=folder.id_, infohash=database_blob(random_infohash()))
    assert (0, channel.id_, folder.id_) == torrent.get_parents_ids()


@db_session
def test_process_payload_with_known_channel_public_key(metadata_store):
    """
    Test processing a payload when the channel public key is known, e.g. from disk.
    """
    key1 = default_eccrypto.generate_key("curve25519")
    key2 = default_eccrypto.generate_key("curve25519")
    torrent = metadata_store.TorrentMetadata(infohash=database_blob(random_infohash()), sign_with=key1)
    payload = torrent._payload_class(**torrent.to_dict())
    torrent.delete()
    # Check rejecting a payload with non-matching public key
    assert [(None, NO_ACTION)] == metadata_store.process_payload(
        payload, channel_public_key=key2.pub().key_to_bin()[10:]
    )
    # Check accepting a payload with matching public key
    assert (
        UNKNOWN_TORRENT
        == metadata_store.process_payload(payload, channel_public_key=key1.pub().key_to_bin()[10:])[0][1]
    )


@db_session
def test_process_payload_reject_older(metadata_store):
    # Check there is no action if the processed payload has a timestamp that is less than the
    # local_version of the corresponding local channel. (I.e. remote peer trying to push back a deleted entry)
    channel = metadata_store.ChannelMetadata(
        title='bla', version=123, timestamp=12, local_version=12, infohash=database_blob(random_infohash())
    )
    torrent = metadata_store.TorrentMetadata(
        title='blabla', timestamp=11, origin_id=channel.id_, infohash=database_blob(random_infohash())
    )
    payload = torrent._payload_class(**torrent.to_dict())
    torrent.delete()
    assert [(None, NO_ACTION)] == metadata_store.process_payload(payload, skip_personal_metadata_payload=False)

    # Now test the same, but for a torrent within a hierarchy of nested channel
    folder_1 = metadata_store.CollectionNode(origin_id=channel.id_)
    folder_2 = metadata_store.CollectionNode(origin_id=folder_1.id_)

    torrent = metadata_store.TorrentMetadata(
        title='blabla', timestamp=11, origin_id=folder_2.id_, infohash=database_blob(random_infohash())
    )
    payload = torrent._payload_class(**torrent.to_dict())
    torrent.delete()
    assert [(None, NO_ACTION)] == metadata_store.process_payload(payload, skip_personal_metadata_payload=False)

    # Now test that we still add the torrent for the case of a broken hierarchy
    folder_1 = metadata_store.CollectionNode(origin_id=123123)
    folder_2 = metadata_store.CollectionNode(origin_id=folder_1.id_)
    torrent = metadata_store.TorrentMetadata(
        title='blabla', timestamp=11, origin_id=folder_2.id_, infohash=database_blob(random_infohash())
    )
    payload = torrent._payload_class(**torrent.to_dict())
    torrent.delete()
    assert UNKNOWN_TORRENT == metadata_store.process_payload(payload, skip_personal_metadata_payload=False)[0][1]


@db_session
def test_process_payload_reject_older_entry(metadata_store):
    """
    Test rejecting and returning GOT_NEWER_VERSION upon receiving an older version
    of an already known metadata entry
    """
    torrent_old = metadata_store.TorrentMetadata(
        title='blabla', timestamp=11, id_=3, infohash=database_blob(random_infohash())
    )
    payload_old = torrent_old._payload_class(**torrent_old.to_dict())
    torrent_old.delete()

    torrent_updated = metadata_store.TorrentMetadata(
        title='blabla', timestamp=12, id_=3, infohash=database_blob(random_infohash())
    )
    # Test rejecting older version of the same entry
    assert [(torrent_updated, GOT_NEWER_VERSION)] == metadata_store.process_payload(
        payload_old, skip_personal_metadata_payload=False
    )


@db_session
def test_get_num_channels_nodes(metadata_store):
    metadata_store.ChannelMetadata(title='testchan', id_=0, infohash=database_blob(random_infohash()))
    metadata_store.ChannelMetadata(title='testchan', id_=123, infohash=database_blob(random_infohash()))
    metadata_store.ChannelMetadata(
        title='testchan',
        id_=0,
        public_key=unhexlify('0' * 20),
        signature=unhexlify('0' * 64),
        skip_key_check=True,
        infohash=database_blob(random_infohash()),
    )
    metadata_store.ChannelMetadata(
        title='testchan',
        id_=0,
        public_key=unhexlify('1' * 20),
        signature=unhexlify('1' * 64),
        skip_key_check=True,
        infohash=database_blob(random_infohash()),
    )

    _ = [
        metadata_store.TorrentMetadata(title='test' + str(x), status=NEW, infohash=database_blob(random_infohash()))
        for x in range(0, 3)
    ]

    assert metadata_store.get_num_channels() == 4
    assert metadata_store.get_num_torrents() == 3


@db_session
def test_process_payload_update_type(metadata_store):
    # Check if applying class-changing update to an entry works
    # First, create a node and get a payload from it, then update it to another type, then get payload
    # for the updated version, then delete the updated version, then bring back the original one by processing it,
    # then try processing the payload of updated version and see if it works. Phew!
    node, node_payload, node_deleted_payload = get_payloads(metadata_store.CollectionNode)
    updated_node = node.update_properties({"origin_id": 0})  # This will implicitly change the node to ChannelTorrent
    assert updated_node.metadata_type == CHANNEL_TORRENT
    updated_node_payload = updated_node._payload_class.from_signed_blob(updated_node.serialized())
    updated_node.delete()

    old_node, _ = metadata_store.process_payload(node_payload, skip_personal_metadata_payload=False)[0]
    updated_node2, _ = metadata_store.process_payload(updated_node_payload, skip_personal_metadata_payload=False)[0]
    assert updated_node2.metadata_type == CHANNEL_TORRENT
