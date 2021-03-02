import hashlib
from binascii import unhexlify

from pony.orm import db_session

import pytest

from tribler_core.modules.metadata_store.orm_bindings.binary_data import InvalidHashException

PNG_DATA = unhexlify(
    "89504e470d0a1a0a0000000d494844520"
    "0000001000000010100000000376ef924"
    "0000001049444154789c626001000000f"
    "fff03000006000557bfabd40000000049454e44ae426082"
)


@db_session
def test_wrong_hash_exception(metadata_store):
    # Check that creating an entry with hash that doesn't match the data raises an error
    with pytest.raises(InvalidHashException):
        metadata_store.BinaryData(hash=b"0000", data=b"aaaa")


@db_session
def test_create_binary_data_entry(metadata_store):
    # Check that the hash value is calculated correctly and data is stored by it
    d = b"bbbb"
    metadata_store.BinaryData(data=d)
    hsh = hashlib.sha1(d).digest()
    assert metadata_store.BinaryData.get(hash=hsh).data == d


@db_session
def test_content_type_detection(metadata_store):
    # Check that content type is properly detected from binary data
    assert metadata_store.BinaryData(data=PNG_DATA).content_type == "image/png"
