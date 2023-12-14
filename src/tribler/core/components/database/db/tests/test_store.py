import random
import string
import threading
from datetime import datetime

import pytest
from ipv8.keyvault.crypto import default_eccrypto
from pony.orm import db_session

from tribler.core.components.database.db.orm_bindings.torrent_metadata import entries_to_chunk
from tribler.core.components.database.db.serialization import (
    SignedPayload,
    int2time,
)
from tribler.core.components.database.db.store import ObjState
from tribler.core.utilities.pony_utils import run_threaded
from tribler.core.utilities.utilities import random_infohash


# pylint: disable=protected-access,unused-argument


def get_payloads(entity_class, key):
    c = entity_class(infohash=random_infohash())
    payload = c.payload_class.from_signed_blob(c.serialized())
    return c, payload


def make_wrong_payload(filename):
    key = default_eccrypto.generate_key("curve25519")
    metadata_payload = SignedPayload(666, 0, key.pub().key_to_bin()[10:], signature=b'\x00' * 64, skip_key_check=True)
    with open(filename, 'wb') as output_file:
        output_file.write(metadata_payload.serialized())


@db_session
def test_squash_mdblobs(metadata_store):
    r = random.Random(123)
    chunk_size = metadata_store.TorrentMetadata._CHUNK_SIZE_LIMIT
    md_list = [
        metadata_store.TorrentMetadata(
            title=''.join(r.choice(string.ascii_uppercase + string.digits) for _ in range(20)),
            infohash=random_infohash(),
            torrent_date=datetime.utcfromtimestamp(100),
        )
        for _ in range(0, 10)
    ]
    chunk, _ = entries_to_chunk(md_list, chunk_size=chunk_size)
    dict_list = [d.to_dict()["signature"] for d in md_list]
    for d in md_list:
        d.delete()
    assert dict_list == [
        d.md_obj.to_dict()["signature"]
        for d in metadata_store.process_compressed_mdblob(chunk, skip_personal_metadata_payload=False)
    ]


@db_session
def test_squash_mdblobs_multiple_chunks(metadata_store):
    rng = random.Random(123)
    md_list = [
        metadata_store.TorrentMetadata(
            title=''.join(rng.choice(string.ascii_uppercase + string.digits) for _ in range(20)),
            infohash=random_infohash(rng),
            id_=rng.randint(0, 100000000),
            torrent_date=int2time(rng.randint(0, 4000000)),
            timestamp=rng.randint(0, 100000000),
        )
        for _ in range(0, 10)
    ]
    for md in md_list:
        md.public_key = metadata_store.my_public_key_bin
        md.signature = md.serialized(metadata_store.my_key)[-64:]
    # Test splitting into multiple chunks
    chunk, index = entries_to_chunk(md_list, chunk_size=900)
    chunk2, _ = entries_to_chunk(md_list, chunk_size=900, start_index=index)
    dict_list = [d.to_dict()["signature"] for d in md_list]
    for d in md_list:
        d.delete()
    assert dict_list[:index] == [
        d.md_obj.to_dict()["signature"]
        for d in metadata_store.process_compressed_mdblob(chunk, skip_personal_metadata_payload=False)
    ]

    assert dict_list[index:] == [
        d.md_obj.to_dict()["signature"]
        for d in metadata_store.process_compressed_mdblob(chunk2, skip_personal_metadata_payload=False)
    ]


@db_session
def test_skip_processing_mdblob_with_forbidden_terms(metadata_store):
    """
    Test that an mdblob with forbidden terms cannot ever get into the local database
    """
    key = default_eccrypto.generate_key("curve25519")
    chan_entry = metadata_store.TorrentMetadata(title="12yo", infohash=random_infohash())
    chan_payload = chan_entry.payload_class.from_dict(**chan_entry.to_dict())
    chan_payload.add_signature(key)
    chan_entry.delete()
    assert metadata_store.process_payload(chan_payload) == []


@db_session
def test_process_invalid_compressed_mdblob(metadata_store):
    """
    Test whether processing an invalid compressed mdblob does not crash Tribler
    """
    assert not metadata_store.process_compressed_mdblob(b"abcdefg")


@db_session
def test_process_forbidden_payload(metadata_store):
    _, node_payload = get_payloads(
        metadata_store.TorrentMetadata, default_eccrypto.generate_key("curve25519")
    )

    assert metadata_store.process_payload(node_payload) == []


@db_session
def test_process_payload(metadata_store):
    sender_key = default_eccrypto.generate_key("curve25519")
    node, node_payload = get_payloads(metadata_store.TorrentMetadata, sender_key)
    node_payload.add_signature(sender_key)
    node_dict = node.to_dict()
    node.delete()

    # Check if node metadata object is properly created on payload processing
    result, = metadata_store.process_payload(node_payload)
    assert result.obj_state == ObjState.NEW_OBJECT
    assert node_dict['metadata_type'] == result.md_obj.to_dict()['metadata_type']

    # Check that we flag this as duplicate in case we already know about the local node
    result, = metadata_store.process_payload(node_payload)
    assert result.obj_state == ObjState.DUPLICATE_OBJECT


@db_session
def test_process_payload_invalid_sig(metadata_store):
    sender_key = default_eccrypto.generate_key("curve25519")
    node, node_payload = get_payloads(metadata_store.TorrentMetadata, sender_key)
    node_payload.add_signature(sender_key)
    node_payload.signature = bytes(127 ^ byte for byte in node_payload.signature)
    node.delete()

    assert [] == metadata_store.process_payload(node_payload)


@db_session
def test_process_payload_invalid_metadata_type(metadata_store):
    sender_key = default_eccrypto.generate_key("curve25519")
    node, node_payload = get_payloads(metadata_store.TorrentMetadata, sender_key)
    node_payload.metadata_type = -1
    node.delete()

    assert [] == metadata_store.process_payload(node_payload)


@db_session
def test_process_payload_skip_personal(metadata_store):
    sender_key = default_eccrypto.generate_key("curve25519")
    metadata_store.my_public_key_bin = sender_key.pub().key_to_bin()[10:]
    node, node_payload = get_payloads(metadata_store.TorrentMetadata, sender_key)
    node_payload.add_signature(sender_key)
    node.delete()

    assert [] == metadata_store.process_payload(node_payload)


@db_session
def test_process_payload_unsigned(metadata_store):
    sender_key = default_eccrypto.generate_key("curve25519")
    node, node_payload = get_payloads(metadata_store.TorrentMetadata, sender_key)
    node_dict = node.to_dict()
    infohash = node_dict['infohash']
    node.delete()

    # Check if node metadata object is properly created on payload processing
    result, = metadata_store.process_payload(node_payload)
    assert result.obj_state == ObjState.NEW_OBJECT
    assert node_dict['metadata_type'] == result.md_obj.to_dict()['metadata_type']

    # Check that nothing happens in case we don't know about the local node
    assert metadata_store.process_payload(node_payload) == []


@db_session
def test_process_payload_ffa(metadata_store):
    infohash = b"1" * 20
    ffa_title = "abcabc"
    ffa_torrent = metadata_store.TorrentMetadata.add_ffa_from_dict(dict(infohash=infohash, title=ffa_title))
    ffa_payload = metadata_store.TorrentMetadata.payload_class.from_signed_blob(ffa_torrent.serialized())
    ffa_torrent.delete()

    # Assert that FFA is never added to DB if there is already a signed entry with the same infohash
    signed_md = metadata_store.TorrentMetadata(infohash=infohash, title='')
    metadata_store.TorrentMetadata.payload_class.from_signed_blob(signed_md.serialized())
    assert metadata_store.process_payload(ffa_payload) == []
    assert metadata_store.TorrentMetadata.get(title=ffa_title) is None
    signed_md.delete()

    # Add an FFA from the payload
    result = metadata_store.process_payload(ffa_payload)[0]
    assert result.obj_state == ObjState.NEW_OBJECT
    assert metadata_store.TorrentMetadata.get(title=ffa_title)

    # Assert that older FFAs are never replaced by newer ones with the same infohash
    assert metadata_store.process_payload(ffa_payload) == []


class ThreadedTestException(Exception):
    pass


async def test_run_threaded(metadata_store):
    thread_id = threading.get_ident()

    def f1(a, b, *, c, d):
        if a == 1 and b == 2 and c == 3 and d == 4:
            return threading.get_ident()
        raise ThreadedTestException('test exception')

    result = await run_threaded(metadata_store.db, f1, 1, 2, c=3, d=4)
    assert result != thread_id

    with pytest.raises(ThreadedTestException, match='^test exception$'):
        await run_threaded(metadata_store.db, f1, 1, 2, c=5, d=6)


def test_get_entries_query_sort_by_size(metadata_store):
    with db_session:
        metadata_store.TorrentMetadata.add_ffa_from_dict({"infohash": b"\xab" * 20, "title": "abc", "size": 20})
        metadata_store.TorrentMetadata.add_ffa_from_dict({"infohash": b"\xcd" * 20, "title": "def", "size": 1})
        metadata_store.TorrentMetadata.add_ffa_from_dict({"infohash": b"\xef" * 20, "title": "ghi", "size": 10})

        ordered1, ordered2, ordered3 = metadata_store.get_entries_query(sort_by="size", sort_desc=True)[:]
        assert ordered1.size == 20
        assert ordered2.size == 10
        assert ordered3.size == 1
