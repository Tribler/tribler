from __future__ import annotations

from ipv8.messaging.anonymization.payload import CellablePayload
from ipv8.messaging.lazy_payload import vp_compile


@vp_compile
class HTTPRequestPayload(CellablePayload):
    """
    A request to an HTTP address.
    """

    msg_id = 28
    format_list = ["I", "I", "address", "varlenH"]
    names = ["circuit_id", "identifier", "target", "request"]

    circuit_id: int
    identifier: int
    target: tuple[str, int]
    request: bytes


@vp_compile
class HTTPResponsePayload(CellablePayload):
    """
    A response after executing an HTTP request.
    """

    msg_id = 29
    format_list = ["I", "I", "H", "H", "varlenH"]
    names = ["circuit_id", "identifier", "part", "total", "response"]

    circuit_id: int
    identifier: int
    part: int
    total: int
    response: bytes
