from __future__ import absolute_import

import time
from binascii import unhexlify
from random import choice, randint, uniform

from six.moves import xrange

from Tribler.Core.Utilities.unicode import hexlify
from Tribler.Test.GUI.FakeTriblerAPI.constants import COMMITTED
from Tribler.Test.GUI.FakeTriblerAPI.utils import get_random_filename, get_random_hex_string


class Torrent(object):

    def __init__(self, infohash, name, length, category, status=COMMITTED):
        self.infohash = infohash
        self.name = name
        self.length = length
        self.category = category
        self.files = []
        self.time_added = randint(1200000000, 1460000000)
        self.relevance_score = uniform(0, 20)
        self.status = status
        self.trackers = []
        self.last_tracker_check = 0
        self.num_seeders = 0
        self.num_leechers = 0
        self.updated = int(time.time())

        if randint(0, 1) == 0:
            # Give this torrent some health
            self.update_health()

        for ind in range(randint(0, 10)):
            self.trackers.append("https://tracker%d.org" % ind)

    def update_health(self):
        self.last_tracker_check = randint(int(time.time()) - 3600 * 24 * 30, int(time.time()))
        self.num_seeders = randint(0, 500) if randint(0, 1) == 0 else 0
        self.num_leechers = randint(0, 500) if randint(0, 1) == 0 else 0

    def get_json(self, include_status=False, include_trackers=False):
        result = {
            "name": self.name,
            "infohash": hexlify(self.infohash),
            "size": self.length,
            "category": self.category,
            "relevance_score": self.relevance_score,
            "num_seeders": self.num_seeders,
            "num_leechers": self.num_leechers,
            "last_tracker_check": self.last_tracker_check,
            "updated": self.updated
        }

        if include_status:
            result["status"] = self.status

        if include_trackers:
            result["trackers"] = self.trackers

        return result

    @staticmethod
    def random():
        infohash = unhexlify(get_random_hex_string(40))
        name = get_random_filename()
        categories = ['document', 'audio', 'video', 'xxx']
        torrent = Torrent(infohash, name, randint(1024, 1024 * 3000), choice(categories))

        # Create the files
        for _ in xrange(randint(1, 20)):
            torrent.files.append({"path": get_random_filename(), "length": randint(1024, 1024 * 3000)})

        return torrent
