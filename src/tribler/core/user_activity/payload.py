from __future__ import annotations

from ipv8.messaging.lazy_payload import VariablePayloadWID, vp_compile


@vp_compile
class InfohashPreferencePayload(VariablePayloadWID):
    """
    A network payload containing a query and corresponding infohashes with their perceived preference.
    """

    msg_id = 1

    names = ["query", "infohashes", "weights"]
    format_list = ["varlenHutf8", "varlenHx20", "arrayH-d"]

    query: str
    infohashes: list[bytes]
    weights: list[float]

    @classmethod
    def fix_unpack_infohashes(cls, wire_value: bytes) -> list[bytes]:
        """
        Convert the wire-format to a list of 20 byte values.
        """
        return [wire_value[i:i + 20] for i in range(0, len(wire_value), 20)]

    def fix_pack_infohashes(self, user_value: list[bytes]) -> bytes:
        """
        Convert a list of bytest to one big bytes.
        """
        return b"".join(user_value)

@vp_compile
class PullPreferencePayload(VariablePayloadWID):
    """
    Ask for a random preference.
    """

    msg_id = 2

    names = ["mid"]
    format_list = ["varlenH"]

    mid: bytes
