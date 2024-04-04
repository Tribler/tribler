from ipv8.messaging.lazy_payload import VariablePayload, vp_compile


@vp_compile
class StatementOperation(VariablePayload):
    """
    Do not change the format of the StatementOperation, because this will result in an invalid signature.
    """
    names = ["subject_type", "subject", "predicate", "object", "operation", "clock", "creator_public_key"]
    format_list = ["q", "varlenHutf8", "q", "varlenHutf8", "q", "q", "74s"]

    subject_type: int  # ResourceType enum
    subject: str
    predicate: int  # ResourceType enum
    object: str
    operation: int  # Operation enum
    clock: int  # This is the lamport-like clock that unique for each quadruple {public_key, subject, predicate, object}
    creator_public_key: bytes


@vp_compile
class StatementOperationSignature(VariablePayload):
    names = ["signature"]
    format_list = ["64s"]

    signature: bytes


@vp_compile
class RawStatementOperationMessage(VariablePayload):
    """
    RAW payload class is used for reducing ipv8 unpacking operations
    For more information take a look at: https://github.com/Tribler/tribler/pull/6396#discussion_r728334323
    """
    names = ["operation", "signature"]
    format_list = ["varlenH", "varlenH"]

    operation: bytes
    signature: bytes
    msg_id = 2


@vp_compile
class StatementOperationMessage(VariablePayload):
    names = ["operation", "signature"]
    format_list = [StatementOperation, StatementOperationSignature]

    operation: bytes
    signature: bytes
    msg_id = 2


@vp_compile
class RequestStatementOperationMessage(VariablePayload):
    names = ["count"]
    format_list = ["q"]

    count: int
    msg_id = 1
