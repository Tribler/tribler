from dataclasses import dataclass
from enum import IntEnum

from ipv8.messaging.payload_dataclass import overwrite_dataclass, type_from_format
from tribler_common.tag_constants import MAX_TAG_LENGTH, MIN_TAG_LENGTH

dataclass = overwrite_dataclass(dataclass)


class TagOperationEnum(IntEnum):
    ADD = 1
    REMOVE = 2


@dataclass
class TagOperation:
    """Do not change the format of the TagOperationMessage, because this will result in an invalid signature.
    """
    infohash: type_from_format('20s')
    operation: int
    clock: int  # this is the lamport-like clock that unique for each triple {public_key, infohash, tag}
    creator_public_key: type_from_format('74s')
    tag: str

    def validate(self):
        assert MIN_TAG_LENGTH <= len(self.tag) <= MAX_TAG_LENGTH, 'Tag length should be in range [3..50]'
        assert not any(ch.isupper() for ch in self.tag), 'Tag should not contain upper-case letters'
        assert ' ' not in self.tag, 'Tag should not contain any spaces'

        # try to convert operation into Enum
        assert TagOperationEnum(self.operation)


RAW_DATA = type_from_format('varlenH')
TAG_OPERATION_MESSAGE_ID = 1


@dataclass
class TagOperationSignature:
    signature: type_from_format('64s')


@dataclass(msg_id=TAG_OPERATION_MESSAGE_ID)
class RawTagOperationMessage:
    """ RAW payload class is used for reducing ipv8 unpacking operations
    For more information take a look at: https://github.com/Tribler/tribler/pull/6396#discussion_r728334323
    """
    operation: RAW_DATA
    signature: RAW_DATA


@dataclass(msg_id=TAG_OPERATION_MESSAGE_ID)
class TagOperationMessage:
    operation: TagOperation
    signature: TagOperationSignature


@dataclass(msg_id=2)
class RequestTagOperationMessage:
    count: int
