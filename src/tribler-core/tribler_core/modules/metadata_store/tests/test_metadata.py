from ipv8.database import database_blob
from ipv8.keyvault.crypto import default_eccrypto

from pony import orm
from pony.orm import db_session

import pytest

from tribler_core.exceptions import InvalidChannelNodeException, InvalidSignatureException
from tribler_core.modules.metadata_store.serialization import (
    CHANNEL_NODE,
    ChannelNodePayload,
    KeysMismatchException,
    NULL_KEY,
    NULL_SIG,
)
from tribler_core.utilities.unicode import hexlify


@db_session
def test_to_dict(metadata_store):
    """
    Test whether converting metadata to a dictionary works
    """
    metadata = metadata_store.ChannelNode.from_dict({})
    assert metadata.to_dict()


@db_session
def test_serialization(metadata_store):
    """
    Test converting metadata to serialized data and back
    """
    for md_type in [metadata_store.ChannelNode, metadata_store.MetadataNode, metadata_store.CollectionNode]:
        metadata1 = md_type()
        serialized1 = metadata1.serialized()
        metadata1.delete()
        orm.flush()

        metadata2 = md_type.from_payload(md_type._payload_class.from_signed_blob(serialized1))
        serialized2 = metadata2.serialized()
        assert serialized1 == serialized2

        # Test no signature exception
        metadata2_dict = metadata2.to_dict()
        metadata2_dict.pop("signature")
        with pytest.raises(InvalidSignatureException):
            md_type._payload_class(**metadata2_dict)

        serialized3 = serialized2[:-5] + b"\xee" * 5
        with pytest.raises(InvalidSignatureException):
            md_type._payload_class.from_signed_blob(serialized3)
        # Test bypass signature check
        md_type._payload_class.from_signed_blob(serialized3, check_signature=False)


@db_session
def test_ffa_serialization(metadata_store):
    """
    Test converting free-for-all (unsigned) torrent metadata to payload and back
    """
    metadata1 = metadata_store.ChannelNode.from_dict({"public_key": b"", "id_": "123"})
    serialized1 = metadata1.serialized()
    # Make sure sig is really zeroes
    assert hexlify(serialized1).endswith(hexlify(NULL_SIG))
    metadata1.delete()
    orm.flush()

    metadata2 = metadata_store.ChannelNode.from_payload(ChannelNodePayload.from_signed_blob(serialized1))
    serialized2 = metadata2.serialized()
    assert serialized1 == serialized2

    # Check that it is impossible to create FFA node without specifying id_
    with pytest.raises(InvalidChannelNodeException):
        metadata_store.ChannelNode.from_dict({"public_key": b""})
    # Check that it is impossible to create FFA payload with non-null signature
    with pytest.raises(InvalidSignatureException):
        ChannelNodePayload(CHANNEL_NODE, 0, NULL_KEY, 0, 0, 0, signature=b"123")
    # Check that creating a pair of metadata entries do not trigger uniqueness constraints error
    metadata_store.ChannelNode.from_dict({"public_key": b"", "id_": "124"})
    metadata_store.ChannelNode.from_dict({"public_key": b"", "id_": "125"})


@db_session
def test_key_mismatch_exception(metadata_store):
    mismatched_key = default_eccrypto.generate_key(u"curve25519")
    metadata = metadata_store.ChannelNode.from_dict({})
    with pytest.raises(KeysMismatchException):
        metadata.serialized(key=mismatched_key)


@db_session
def test_to_file(tmpdir, metadata_store):
    """
    Test writing metadata to a file
    """
    metadata = metadata_store.ChannelNode.from_dict({})
    file_path = tmpdir / 'metadata.file'
    metadata.to_file(file_path)
    assert file_path.exists()


@db_session
def test_has_valid_signature(metadata_store):
    """
    Test whether a signature can be validated correctly
    """
    metadata = metadata_store.ChannelNode.from_dict({})
    assert metadata.has_valid_signature()

    md_dict = metadata.to_dict()

    # Mess with the signature
    metadata.signature = b'a'
    assert not metadata.has_valid_signature()

    # Create metadata with wrong key
    metadata.delete()
    md_dict.update(public_key=database_blob(b"aaa"))
    md_dict.pop("rowid")

    metadata = metadata_store.ChannelNode(skip_key_check=True, **md_dict)
    assert not metadata.has_valid_signature()

    key = default_eccrypto.generate_key(u"curve25519")
    metadata2 = metadata_store.ChannelNode(sign_with=key, **md_dict)
    assert database_blob(key.pub().key_to_bin()[10:]), metadata2.public_key
    md_dict2 = metadata2.to_dict()
    md_dict2["signature"] = md_dict["signature"]
    with pytest.raises(InvalidSignatureException):
        metadata_store.ChannelNode(**md_dict2)


@db_session
def test_from_payload(metadata_store):
    """
    Test converting a metadata payload to a metadata object
    """
    metadata = metadata_store.ChannelNode.from_dict({})
    metadata_dict = metadata.to_dict()
    metadata.delete()
    orm.flush()
    metadata_payload = ChannelNodePayload(**metadata_dict)
    assert metadata_store.ChannelNode.from_payload(metadata_payload)
