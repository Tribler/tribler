from random import randint, uniform, random
from constants import DLSTATUS_STRINGS


class Download:

    def __init__(self, torrent):
        self.torrent = torrent
        self.status = randint(0, 8)
        self.anon = True if randint(0, 1) == 0 else False
        self.anon_hops = randint(1, 3) if self.anon else 0
        self.safe_seeding = True if randint(0, 1) == 0 else False
        self.peers = randint(0, 1000)
        self.seeds = randint(0, 1000)
        self.progress = uniform(0, 1)
        self.down_speed = randint(0, 1000000)
        self.up_speed = randint(0, 1000000)
        self.files = []
        self.trackers = [{"url": "[PEX]", "status": "working", "peers": 42}]

        # Generate some files
        for file_ind in xrange(randint(1, 10)):
            self.files.append({"name": "File %d" % file_ind, "size": randint(1000, 10000000),
                               "progress": random(), "included": True if random() > 0.5 else False})

    def get_json(self):
        return {"name": self.torrent.name, "infohash": self.torrent.infohash, "status": DLSTATUS_STRINGS[self.status],
                "num_peers": self.peers, "num_seeds": self.seeds, "progress": self.progress,
                "size": self.torrent.length, "speed_down": self.down_speed, "speed_up": self.up_speed, "eta": 1234,
                "hops": self.anon_hops, "anon_download": self.anon, "files": self.files, "trackers": self.trackers}
