from __future__ import annotations

from typing import Self

from ipv8.messaging.lazy_payload import VariablePayload, vp_compile

from tribler.core.torrent_checker.healthdataclasses import HealthInfo


@vp_compile
class HealthRequestPayload(VariablePayload):
    """
    A request to be sent the health information of torrents.
    """

    msg_id = 3
    format_list = ["B"]
    names = ["request_type"]

    request_type: int


@vp_compile
class HealthFormat(VariablePayload):
    """
    A payload for torrent health information.
    """

    format_list = ["20s", "I", "I", "Q", "varlenHutf8"]
    names = ["infohash", "seeders", "leechers", "timestamp", "tracker"]

    infohash: bytes
    seeders: int
    leechers: int
    timestamp: int
    tracker: str


@vp_compile
class HealthPayload(VariablePayload):
    """
    A payload for a list of torrent health information.
    """

    msg_id = 4
    format_list = ["B", [HealthFormat], "raw"]
    names = ["response_type", "torrents", "extra_bytes"]

    response_type: int
    torrents: list[HealthFormat]

    @classmethod
    def create(cls: type[Self], request_type: int, health_infos: list[HealthInfo],) -> Self:
        """
        Create a payload from the given list.
        """
        # Since the tracker field can be a large string, limit the number of items that we add to the payload.
        # This should lower the risk of UDP packet fragmentation.
        size = 0
        return cls(request_type, [HealthFormat(h.infohash, h.seeders, h.leechers, h.last_check, h.tracker)
                                  for h in health_infos if (size := size + len(h.tracker) + 38) <= 1200], b"")

    def get_health_info(self) -> list[HealthInfo]:
        """
        Gets the list of HealthInfo objects.
        """
        return [HealthInfo(infohash=t.infohash, last_check=t.timestamp, tracker=t.tracker,
                           seeders=t.seeders, leechers=t.leechers) for t in self.torrents]


@vp_compile
class VersionRequest(VariablePayload):
    """
    A request for the Tribler version and Operating System of a peer.
    """

    msg_id = 101


@vp_compile
class VersionResponse(VariablePayload):
    """
    A response to a request for Tribler version and OS.
    """

    msg_id = 102
    format_list = ["varlenI", "varlenI"]
    names = ["version", "platform"]

    version: str
    platform: str

    def fix_pack_version(self, value: str) -> bytes:
        """
        Convert the (utf-8) Tribler version string to bytes.
        """
        return value.encode()

    def fix_pack_platform(self, value: str) -> bytes:
        """
        Convert the (utf-8) platform description string to bytes.
        """
        return value.encode()

    @classmethod
    def fix_unpack_version(cls: type[Self], value: bytes) -> str:
        """
        Convert the packed Tribler version back to a string.
        """
        return value.decode()

    @classmethod
    def fix_unpack_platform(cls: type[Self], value: bytes) -> str:
        """
        Convert the packed platform description back to a string.
        """
        return value.decode()


@vp_compile
class RemoteSelectPayload(VariablePayload):
    """
    A payload to sent SQL queries to other peers.
    """

    msg_id = 201
    format_list = ["I", "varlenH"]
    names = ["id", "json"]

    id: int
    json: bytes


@vp_compile
class SelectResponsePayload(VariablePayload):
    """
    A response to a select request.
    """

    msg_id = 202
    format_list = ["I", "raw"]
    names = ["id", "raw_blob"]

    id: int
    raw_blob: bytes
