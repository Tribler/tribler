import time
from random import randint, choice

import Tribler.Test.GUI.FakeTriblerAPI.tribler_utils as tribler_utils
from Tribler.Test.GUI.FakeTriblerAPI.constants import NEW, TODELETE
from Tribler.Test.GUI.FakeTriblerAPI.utils import get_random_hex_string


class Channel(object):

    def __init__(self, cid, name="", description=""):
        self.name = name
        self.description = description
        self.id = cid
        self.public_key = get_random_hex_string(64).decode('hex')
        self.votes = randint(0, 10000)
        self.torrents = set()
        self.subscribed = False
        self.state = choice([u"Downloading", u"Personal", u"Legacy", u"Complete", u"Updating", u"Preview"])
        self.timestamp = int(round(time.time() * 1000)) - randint(0, 3600 * 24 * 7 * 1000)

        self.add_random_torrents()

    def add_random_torrents(self):
        all_torrents = tribler_utils.tribler_data.torrents
        num_torrents_in_channel = randint(1, len(all_torrents) - 1)
        for _ in range(0, num_torrents_in_channel):
            self.torrents.add(tribler_utils.tribler_data.torrents[randint(0, len(all_torrents) - 1)])

    def get_json(self):
        return {
            "id": self.id,
            "public_key": self.public_key.encode('hex'),
            "name": self.name,
            "torrents": len(self.torrents),
            "subscribed": self.subscribed,
            "votes": self.votes,
            "status": 1,
            "state": self.state,
            "updated": self.timestamp
        }

    def get_torrent_with_infohash(self, infohash):
        for torrent in self.torrents:
            if torrent.infohash == infohash:
                return torrent
        return None

    def is_dirty(self):
        for torrent in self.torrents:
            if torrent.status == NEW or torrent.status == TODELETE:
                return True
        return False
