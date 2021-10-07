import copy

from cryptography.exceptions import InvalidSignature

from ipv8.keyvault.crypto import default_eccrypto
from ipv8.messaging.lazy_payload import VariablePayload
from ipv8.messaging.serialization import default_serializer
from ipv8.types import Key
from tribler_core.components.tag.community.tag_payload import TagOperationMessage
from tribler_core.components.tag.db.tag_db import Operation


class TagCrypto:
    @staticmethod
    def _pack(message: VariablePayload) -> bytes:
        """ Pack a message to bytes by using default ipv8 serializer
        """
        to_pack = copy.copy(message)
        to_pack.signature = b''  # this field is excluded from signing
        return default_serializer.pack_serializable(to_pack)

    @staticmethod
    def sign(infohash: bytes, tag: str, operation: Operation, time: int, creator_public_key: bytes, key: Key) -> bytes:
        """ Sign arguments by using peer's private key
        """
        message = TagOperationMessage(infohash, operation, time, creator_public_key, b'', tag.encode())
        return default_eccrypto.create_signature(key, TagCrypto._pack(message))

    def validate_signature(self, message: TagOperationMessage):
        """ Validate a signature of incoming message
        """
        assert message.creator_public_key
        key = default_eccrypto.key_from_public_bin(message.creator_public_key)
        if not default_eccrypto.is_valid_signature(key, self._pack(message), message.signature):
            raise InvalidSignature()
