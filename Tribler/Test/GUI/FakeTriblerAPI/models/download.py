from __future__ import absolute_import, division

import base64
from binascii import hexlify
from random import randint, random, uniform

from six.moves import xrange

from Tribler.Test.GUI.FakeTriblerAPI.constants import DLSTATUS_STRINGS
from Tribler.Test.GUI.FakeTriblerAPI.models.download_peer import DownloadPeer


class Download(object):

    def __init__(self, torrent, is_credit_mining=False, is_channel_download=False):
        self.torrent = torrent
        self.status = randint(0, 8)
        self.anon = True if randint(0, 1) == 0 else False
        self.anon_hops = randint(1, 3) if self.anon else 0
        self.safe_seeding = True if randint(0, 1) == 0 else False
        self.num_peers = randint(0, 1000)
        self.seeds = randint(0, 1000)
        self.num_connected_peers = randint(0, 100)
        self.num_connected_seeds = randint(0, 100)
        self.progress = uniform(0, 1)
        self.down_speed = randint(0, 1000000)
        self.up_speed = randint(0, 1000000)
        self.total_up = randint(0, 1000000)
        self.total_down = randint(0, 1000000)
        self.ratio = float(self.total_up) / float(self.total_down)
        self.files = []
        self.trackers = [{"url": "[PEX]", "status": "working", "peers": 42}]
        self.destination = "/"
        self.availability = uniform(0, 5)
        self.peers = []
        self.total_pieces = randint(100, 2000)
        self.has_pieces = [False] * self.total_pieces
        self.time_added = randint(1400000000, 1484819242)
        self.is_credit_mining = is_credit_mining
        self.is_channel_download = is_channel_download

        # Set some pieces to True
        for _ in xrange(self.total_pieces / 2):
            self.has_pieces[randint(0, self.total_pieces - 1)] = True

        for _ in xrange(randint(5, 40)):
            self.peers.append(DownloadPeer())

        # Generate some files
        for file_ind in xrange(randint(1, 10)):
            self.files.append({"name": "File %d" % file_ind, "size": randint(1000, 10000000),
                               "progress": random(), "included": True if random() > 0.5 else False})

    def get_pieces_base64(self):
        bitstr = ""
        for bit in self.has_pieces:
            bitstr += '1' if bit else '0'

        encoded_str = ""
        for i in range(0, len(bitstr), 8):
            encoded_str += chr(int(bitstr[i:i+8].ljust(8, '0'), 2))
        return base64.b64encode(encoded_str)

    def get_json(self, get_peers=False, get_pieces=False):
        download = {
            "name": self.torrent.name,
            "infohash": hexlify(self.torrent.infohash),
            "status": DLSTATUS_STRINGS[self.status],
            "num_peers": self.num_peers,
            "num_seeds": self.seeds,
            "progress": self.progress,
            "size": self.torrent.length,
            "speed_down": self.down_speed,
            "speed_up": self.up_speed,
            "eta": 1234,
            "hops": self.anon_hops,
            "anon_download": self.anon,
            "files": self.files,
            "trackers": self.trackers,
            "destination": self.destination,
            "availability": self.availability,
            "total_pieces": self.total_pieces,
            "total_up": self.total_up,
            "total_down": self.total_down,
            "ratio": self.ratio,
            "error": "unknown",
            "time_added": self.time_added,
            "vod_mode": False,
            "vod_prebuffering_progress_consec": 0.34,
            "credit_mining": self.is_credit_mining,
            "num_connected_peers": self.num_connected_peers,
            "num_connected_seeds": self.num_connected_seeds,
            "channel_download": self.is_channel_download
        }

        if get_peers:
            download["peers"] = [peer.get_info_dict() for peer in self.peers]

        if get_pieces:
            download["pieces"] = self.get_pieces_base64()

        return download
