from dataclasses import dataclass

from ipv8.messaging.payload_dataclass import overwrite_dataclass, type_from_format

dataclass = overwrite_dataclass(dataclass)


@dataclass
class StatementOperation:
    """Do not change the format of the StatementOperation, because this will result in an invalid signature.
    """
    subject_type: int  # ResourceType enum
    subject: str
    predicate: int  # ResourceType enum
    object: str
    operation: int  # Operation enum
    clock: int  # This is the lamport-like clock that unique for each quadruple {public_key, subject, predicate, object}
    creator_public_key: type_from_format('74s')

    def __str__(self):
        return f'({self.subject} {self.predicate} {self.object}), o:{self.operation}, c:{self.clock}))'


RAW_DATA = type_from_format('varlenH')
STATEMENT_OPERATION_MESSAGE_ID = 2


@dataclass
class StatementOperationSignature:
    signature: type_from_format('64s')


@dataclass(msg_id=STATEMENT_OPERATION_MESSAGE_ID)
class RawStatementOperationMessage:
    """ RAW payload class is used for reducing ipv8 unpacking operations
    For more information take a look at: https://github.com/Tribler/tribler/pull/6396#discussion_r728334323
    """
    operation: RAW_DATA
    signature: RAW_DATA


@dataclass(msg_id=STATEMENT_OPERATION_MESSAGE_ID)
class StatementOperationMessage:
    operation: StatementOperation
    signature: StatementOperationSignature


@dataclass(msg_id=1)
class RequestStatementOperationMessage:
    count: int
