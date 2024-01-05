from __future__ import annotations

from ipv8.messaging.lazy_payload import VariablePayload, vp_compile


@vp_compile
class HTTPRequestPayload(VariablePayload):
    msg_id = 28
    format_list = ['I', 'I', 'address', 'varlenH']
    names = ['circuit_id', 'identifier', 'target', 'request']


@vp_compile
class HTTPResponsePayload(VariablePayload):
    msg_id = 29
    format_list = ['I', 'I', 'H', 'H', 'varlenH']
    names = ['circuit_id', 'identifier', 'part', 'total', 'response']
