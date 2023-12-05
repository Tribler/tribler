from typing import List

from ipv8.messaging.lazy_payload import VariablePayload, vp_compile
from ipv8.messaging.payload_dataclass import dataclass
from ipv8.messaging.serialization import default_serializer

from tribler.core.components.torrent_checker.torrent_checker.dataclasses import HealthInfo


@vp_compile
class TorrentInfoFormat(VariablePayload):
    format_list = ['20s', 'I', 'I', 'Q']
    names = ['infohash', 'seeders', 'leechers', 'timestamp']
    length = 36

    def to_tuple(self):
        return self.infohash, self.seeders, self.leechers, self.timestamp

    @classmethod
    def from_list_bytes(cls, serialized):
        return default_serializer.unpack_serializable_list([cls] * (len(serialized) // cls.length),
                                                           serialized, consume_all=False)[:-1]


@vp_compile
class TorrentsHealthPayload(VariablePayload):
    msg_id = 1
    format_list = ['I', 'I', 'varlenI', 'raw']  # Number of random torrents, number of torrents checked by you
    names = ['random_torrents_length', 'torrents_checked_length', 'random_torrents', 'torrents_checked']

    def fix_pack_random_torrents(self, value):
        return b''.join(default_serializer.pack_serializable(TorrentInfoFormat(*sublist)) for sublist in value)

    def fix_pack_torrents_checked(self, value):
        return b''.join(default_serializer.pack_serializable(TorrentInfoFormat(*sublist)) for sublist in value)

    @classmethod
    def fix_unpack_random_torrents(cls, value):
        return [payload.to_tuple() for payload in TorrentInfoFormat.from_list_bytes(value)]

    @classmethod
    def fix_unpack_torrents_checked(cls, value):
        return [payload.to_tuple() for payload in TorrentInfoFormat.from_list_bytes(value)]

    @classmethod
    def create(cls, random_torrents_checked: List[HealthInfo], popular_torrents_checked: List[HealthInfo]):
        random_torrent_tuples = [(health.infohash, health.seeders, health.leechers, health.last_check)
                                 for health in random_torrents_checked]
        popular_torrent_tuples = [(health.infohash, health.seeders, health.leechers, health.last_check)
                                  for health in popular_torrents_checked]
        return cls(len(random_torrents_checked), len(popular_torrents_checked),
                   random_torrent_tuples, popular_torrent_tuples)


@vp_compile
class PopularTorrentsRequest(VariablePayload):
    msg_id=2


@vp_compile
class VersionRequest(VariablePayload):
    msg_id = 101


@vp_compile
class VersionResponse(VariablePayload):
    msg_id = 102
    format_list = ['varlenI', 'varlenI']
    names = ['version', 'platform']

    def fix_pack_version(self, value):
        return value.encode('utf-8')

    def fix_pack_platform(self, value):
        return value.encode('utf-8')

    @classmethod
    def fix_unpack_version(cls, value):
        return value.decode('utf-8')

    @classmethod
    def fix_unpack_platform(cls, value):
        return value.decode('utf-8')


@vp_compile
class RemoteSelectPayload(VariablePayload):
    msg_id = 201
    format_list = ['I', 'varlenH']
    names = ['id', 'json']


@vp_compile
class RemoteSelectPayloadEva(RemoteSelectPayload):
    msg_id = 209


@vp_compile
class SelectResponsePayload(VariablePayload):
    msg_id = 202
    format_list = ['I', 'raw']
    names = ['id', 'raw_blob']
