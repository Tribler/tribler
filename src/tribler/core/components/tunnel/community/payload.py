from __future__ import annotations

from ipv8.messaging.anonymization.payload import CellablePayload
from ipv8.messaging.lazy_payload import vp_compile


@vp_compile
class HTTPRequestPayload(CellablePayload):
    msg_id = 28
    format_list = ['I', 'I', 'address', 'varlenH']
    names = ['circuit_id', 'identifier', 'target', 'request']


@vp_compile
class HTTPResponsePayload(CellablePayload):
    msg_id = 29
    format_list = ['I', 'I', 'H', 'H', 'varlenH']
    names = ['circuit_id', 'identifier', 'part', 'total', 'response']
