from ipv8.messaging.lazy_payload import VariablePayload, vp_compile


@vp_compile
class RequestTagOperationMessage(VariablePayload):
    msg_id = 1

    format_list = ['I']
    names = ['count']


@vp_compile
class TagOperationMessage(VariablePayload):
    msg_id = 2

    format_list = ['20s', 'I', 'I', '74s', '64s', 'raw']
    names = ['infohash', 'operation', 'time', 'creator_public_key', 'signature', 'tag']
