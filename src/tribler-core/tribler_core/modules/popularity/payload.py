from typing import List, TypeVar

from ipv8.messaging.payload_dataclass import dataclass

timestamp_type = TypeVar('Q')


@dataclass(msg_id=1)
class TorrentsHealthPayload:
    @dataclass
    class Torrent:
        infohash: bytes
        seeders: int
        leechers: int
        timestamp: timestamp_type

    random_torrents_length: int
    torrents_checked_length: int
    random_torrents: List[Torrent]
    torrents_checked: List[Torrent]

    @staticmethod
    def create(random_torrents_checked, popular_torrents_checked):
        def to_list(torrents):
            return [TorrentsHealthPayload.Torrent(infohash=t[0], seeders=t[1], leechers=t[2], timestamp=t[3]) for t in
                    torrents]

        return TorrentsHealthPayload(
            random_torrents_length=len(random_torrents_checked),
            torrents_checked_length=len(popular_torrents_checked),
            random_torrents=to_list(random_torrents_checked),
            torrents_checked=to_list(popular_torrents_checked)
        )
