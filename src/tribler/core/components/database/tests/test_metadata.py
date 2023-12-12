import os
from ipv8.keyvault.crypto import default_eccrypto
from pony import orm
from pony.orm import db_session


@db_session
def test_to_dict(metadata_store):
    """
    Test whether converting metadata to a dictionary works
    """
    metadata = metadata_store.TorrentMetadata.from_dict({'infohash': os.urandom(20), 'public_key': b''})
    assert metadata.to_dict()


@db_session
def test_serialization(metadata_store):
    """
    Test converting metadata to serialized data and back
    """
    md_type = metadata_store.TorrentMetadata
    metadata1 = md_type(infohash=os.urandom(20))
    serialized1 = metadata1.serialized(metadata_store.my_key)
    metadata1.delete()
    orm.flush()

    metadata2 = md_type.from_payload(md_type.payload_class.from_signed_blob(serialized1))
    serialized2 = metadata2.serialized()
    assert serialized1 == serialized2

    metadata2_dict = metadata2.to_dict()
    metadata2_dict.pop("signature")
    assert not md_type.payload_class.from_dict(**metadata2_dict).check_signature()

    serialized3 = serialized2[:-5] + b"\xee" * 5
    metadata3 = md_type.payload_class.from_signed_blob(serialized3)
    assert metadata3.has_signature()
    assert not metadata3.check_signature()

    # Test adding a signature and checking for correctness
    key = default_eccrypto.generate_key("curve25519")
    metadata3.add_signature(key)
    assert metadata3.has_signature()
    assert metadata3.check_signature()
    metadata3.signature = os.urandom(64)
    assert metadata3.has_signature()
    assert not metadata3.check_signature()

@db_session
def test_from_payload(metadata_store):
    """
    Test converting a metadata payload to a metadata object
    """
    md_type = metadata_store.TorrentMetadata
    metadata = md_type.from_dict({'infohash': os.urandom(20), 'public_key': b''})
    metadata_dict = metadata.to_dict()
    metadata.delete()
    orm.flush()
    metadata_payload = md_type.payload_class.from_dict(**metadata_dict)
    assert md_type.from_payload(metadata_payload)
