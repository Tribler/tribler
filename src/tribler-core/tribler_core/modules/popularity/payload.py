from ipv8.messaging.lazy_payload import VariablePayload, vp_compile
from ipv8.messaging.serialization import default_serializer


@vp_compile
class TorrentInfoFormat(VariablePayload):
    format_list = ['20s', 'I', 'I', 'Q']
    names = ['infohash', 'seeders', 'leechers', 'timestamp']
    length = 36

    def to_tuple(self):
        return self.infohash, self.seeders, self.leechers, self.timestamp

    @classmethod
    def from_list_bytes(cls, serialized):
        return default_serializer.unpack_serializable_list([cls] * (len(serialized)//cls.length),
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
    def create(cls, random_torrents_checked, popular_torrents_checked):
        return cls(len(random_torrents_checked), len(popular_torrents_checked),
                   random_torrents_checked, popular_torrents_checked)
