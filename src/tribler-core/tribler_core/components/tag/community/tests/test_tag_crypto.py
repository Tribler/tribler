import pytest
from cryptography.exceptions import InvalidSignature

from ipv8.keyvault.crypto import ECCrypto
from ipv8.types import Key
from tribler_core.components.tag.community.tag_crypto import TagCrypto
from tribler_core.components.tag.community.tag_payload import TagOperationMessage
from tribler_core.components.tag.db.tag_db import Operation


# pylint: disable=protected-access

@pytest.fixture(name="tag_crypto")  # this workaround implemented only for pylint
def fixture_tag_crypto():
    return TagCrypto()


@pytest.fixture(name="random_message")  # this workaround implemented only for pylint
def fixture_random_message():
    return TagOperationMessage(f'{1}'.encode() * 20, Operation.ADD, 1, f'{1}'.encode() * 74, f'{1}'.encode() * 64,
                               ''.encode())


@pytest.fixture(name="key")  # this workaround implemented only for pylint
def fixture_key():
    return ECCrypto().generate_key(u"curve25519")


pytestmark = pytest.mark.asyncio


async def test_pack(tag_crypto: TagCrypto, random_message: TagOperationMessage):
    # ensure that signature field doesn't erase
    assert random_message.signature

    assert tag_crypto._pack(random_message)
    assert random_message.signature


async def test_is_signature_valid(tag_crypto: TagCrypto, key: Key):
    infohash = f'{1}'.encode() * 20
    operation = Operation.ADD
    time = 1
    creator_public_key = key.pub().key_to_bin()
    tag = 'tag'

    message = TagOperationMessage(infohash, operation, time, creator_public_key, b'', tag.encode())
    message.signature = tag_crypto.sign(infohash, tag, operation, time, creator_public_key, key)
    tag_crypto.validate_signature(message)


async def test_is_signature_invalid(tag_crypto: TagCrypto, key: Key):
    infohash = f'{1}'.encode() * 20
    operation = Operation.ADD
    time = 1
    creator_public_key = key.pub().key_to_bin()
    tag = 'tag'

    message = TagOperationMessage(infohash, operation, time, creator_public_key, b'', tag.encode())
    message.signature = tag_crypto.sign(infohash, tag, operation, time, creator_public_key, key)
    with pytest.raises(InvalidSignature):
        message.tag = 'changed_tag'.encode()
        tag_crypto.validate_signature(message)
