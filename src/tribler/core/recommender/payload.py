import json
from typing import Any

from ipv8.messaging.lazy_payload import VariablePayloadWID, vp_compile


@vp_compile
class CrawlInfo(VariablePayloadWID):
    """
    A request for crawlable information.
    """

    msg_id = 0

    format_list = ["20s", "raw"]
    names = ["mid", "unknown"]

    mid: bytes
    unknown: bytes


class JSONPayload:
    """
    A generic JSON-based payload.
    """

    format_list = ["20s", "varlenH", "raw"]
    names = ["mid", "data", "unknown"]

    mid: bytes
    data: bytes
    unknown: bytes

    def json(self) -> Any:  # noqa: ANN401
        """
        Convert the data of this object to JSON.
        """
        return json.loads(self.data)


@vp_compile
class Crawl(JSONPayload, VariablePayloadWID):
    """
    A request for crawlable information.
    """

    msg_id = 1


@vp_compile
class CrawlResponse(JSONPayload, VariablePayloadWID):
    """
    A response with crawlable information.
    """

    msg_id = 2
