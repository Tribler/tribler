from __future__ import annotations

from ipv8.messaging.lazy_payload import VariablePayloadWID, vp_compile


@vp_compile
class RecordPayload(VariablePayloadWID):
    """
    A network payload containing a query and corresponding infohashes with their perceived preference.
    """

    msg_id = 1

    names = ["public_key", "ip", "port", "ping", "start", "stop"]
    format_list = ["varlenH", "varlenH", "H", "d", "d", "d"]

    public_key: bytes
    ip: bytes
    port: int
    ping: float
    start: float
    stop: float


@vp_compile
class PullRecordPayload(VariablePayloadWID):
    """
    Ask for a random record.
    """

    msg_id = 2

    names = ["mid"]
    format_list = ["varlenH"]

    mid: bytes
