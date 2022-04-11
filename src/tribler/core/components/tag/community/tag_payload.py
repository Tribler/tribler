from dataclasses import dataclass
from enum import IntEnum

from ipv8.messaging.payload_dataclass import overwrite_dataclass, type_from_format

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

    def __str__(self):
        return f'(t:{self.tag}({self.clock}), o:{self.operation}, i:{self.infohash.hex()})'


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
