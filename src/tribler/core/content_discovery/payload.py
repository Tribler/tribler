from __future__ import annotations

from typing import TYPE_CHECKING

from ipv8.messaging.lazy_payload import VariablePayload, vp_compile
from ipv8.messaging.serialization import default_serializer
from typing_extensions import Self

if TYPE_CHECKING:
    from tribler.core.torrent_checker.dataclasses import HealthInfo


@vp_compile
class TorrentInfoFormat(VariablePayload):
    """
    For a given infohash at a given time: the known seeders and leechers.
    """

    format_list = ["20s", "I", "I", "Q"]
    names = ["infohash", "seeders", "leechers", "timestamp"]
    length = 36

    infohash: bytes
    seeders: int
    leechers: int
    timestamp: int

    def to_tuple(self) -> tuple[bytes, int, int, int]:
        """
        Convert this payload to a tuple.
        """
        return self.infohash, self.seeders, self.leechers, self.timestamp

    @classmethod
    def from_list_bytes(cls: type[Self], serialized: bytes) -> list[Self]:
        """
        Convert the given bytes to a list of this payload.
        """
        return default_serializer.unpack_serializable_list([cls] * (len(serialized) // cls.length),
                                                           serialized, consume_all=False)[:-1]


@vp_compile
class TorrentsHealthPayload(VariablePayload):
    """
    A payload for lists of health information.

    For backward compatibility, this payload includes two lists. Originally, one list was for random torrents and
    one list was for torrents that we personally checked. Now, only one is used.
    """

    msg_id = 1
    format_list = ["I", "I", "varlenI", "raw"]  # Number of random torrents, number of torrents checked by you
    names = ["random_torrents_length", "torrents_checked_length", "random_torrents", "torrents_checked"]

    random_torrents_length: int
    torrents_checked_length: int
    random_torrents: list[tuple[bytes, int, int, int]]
    torrents_checked: list[tuple[bytes, int, int, int]]

    def fix_pack_random_torrents(self, value: list[tuple[bytes, int, int, int]]) -> bytes:
        """
        Convert the list of random torrent info tuples to bytes.
        """
        return b"".join(default_serializer.pack_serializable(TorrentInfoFormat(*sublist)) for sublist in value)

    def fix_pack_torrents_checked(self, value: list[tuple[bytes, int, int, int]]) -> bytes:
        """
        Convert the list of checked torrent info tuples to bytes.
        """
        return b"".join(default_serializer.pack_serializable(TorrentInfoFormat(*sublist)) for sublist in value)

    @classmethod
    def fix_unpack_random_torrents(cls: type[Self], value: bytes) -> list[tuple[bytes, int, int, int]]:
        """
        Convert the raw data back to a list of random torrent info tuples.
        """
        return [payload.to_tuple() for payload in TorrentInfoFormat.from_list_bytes(value)]

    @classmethod
    def fix_unpack_torrents_checked(cls: type[Self], value: bytes) -> list[tuple[bytes, int, int, int]]:
        """
        Convert the raw data back to a list of checked torrent info tuples.
        """
        return [payload.to_tuple() for payload in TorrentInfoFormat.from_list_bytes(value)]

    @classmethod
    def create(cls: type[Self], random_torrents_checked: list[HealthInfo],
               popular_torrents_checked: list[HealthInfo]) -> Self:
        """
        Create a payload from the given lists.
        """
        random_torrent_tuples = [(health.infohash, health.seeders, health.leechers, health.last_check)
                                 for health in random_torrents_checked]
        popular_torrent_tuples = [(health.infohash, health.seeders, health.leechers, health.last_check)
                                  for health in popular_torrents_checked]
        return cls(len(random_torrents_checked), len(popular_torrents_checked), random_torrent_tuples,
                   popular_torrent_tuples)


@vp_compile
class PopularTorrentsRequest(VariablePayload):
    """
    A request to be sent the health information of popular torrents.
    """

    msg_id = 2


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
