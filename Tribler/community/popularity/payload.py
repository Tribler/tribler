from __future__ import absolute_import

import struct

from Tribler.pyipv8.ipv8.messaging.payload import Payload


TORRENT_INFO_FORMAT = '20sIIQ'  # Infohash, seeders, leechers and a timestamp


class TorrentsHealthPayload(Payload):

    format_list = ['I', 'I', 'varlenI', 'raw']  # Number of random torrents, number of torrents checked by you

    def __init__(self, random_torrents, torrents_checked):
        """
        Initialize a TorrentsHealthPayload, containing information on the health of both random torrents and popular
        torrents that have been checked by you.
        :param random_torrents: List of tuple of (infohash, seeders, leechers, checked_timestamp)
        :param torrents_checked: List of tuple of (infohash, seeders, leechers, checked_timestamp)
        """
        super(TorrentsHealthPayload, self).__init__()
        self.random_torrents = random_torrents
        self.torrents_checked = torrents_checked

    def to_pack_list(self):
        random_torrents_items = [item for sublist in self.random_torrents for item in sublist]
        checked_torrents_items = [item for sublist in self.torrents_checked for item in sublist]
        data = [('I', len(self.random_torrents)),
                ('I', len(self.torrents_checked)),
                ('varlenI', struct.pack("!" + TORRENT_INFO_FORMAT * len(self.random_torrents), *random_torrents_items)),
                ('raw', struct.pack("!" + TORRENT_INFO_FORMAT * len(self.torrents_checked), *checked_torrents_items))]

        return data

    @classmethod
    def from_unpack_list(cls, *args):
        num_random_torrents, num_checked_torrents, raw_random_torrents, raw_checked_torrents = args

        random_torrents_list = struct.unpack("!" + TORRENT_INFO_FORMAT * num_random_torrents, raw_random_torrents)
        checked_torrents_list = struct.unpack("!" + TORRENT_INFO_FORMAT * num_checked_torrents, raw_checked_torrents)

        random_torrents = []
        checked_torrents = []
        for ind in range(num_random_torrents):
            random_torrents.append((random_torrents_list[ind * 4],
                                    random_torrents_list[ind * 4 + 1],
                                    random_torrents_list[ind * 4 + 2],
                                    random_torrents_list[ind * 4 + 3]))

        for ind in range(num_checked_torrents):
            checked_torrents.append((checked_torrents_list[ind * 4],
                                     checked_torrents_list[ind * 4 + 1],
                                     checked_torrents_list[ind * 4 + 2],
                                     checked_torrents_list[ind * 4 + 3]))

        return TorrentsHealthPayload(random_torrents, checked_torrents)
