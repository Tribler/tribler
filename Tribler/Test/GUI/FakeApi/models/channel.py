from random import randint, uniform, sample

import tribler_utils
from models.playlist import Playlist
from utils import get_random_hex_string


class Channel:

    def __init__(self, id, name="", description=""):
        self.name = name
        self.description = description
        self.id = id
        self.cid = get_random_hex_string(40)
        self.votes = randint(0, 10000)
        self.spam_votes = randint(0, 10000)
        self.modified = randint(10, 10000)
        self.torrents = set()
        self.subscribed = False
        self.playlists = set()
        self.relevance_score = uniform(0, 5)

        self.add_random_torrents()
        self.generate_playlist()

    def add_random_torrents(self):
        all_torrents = tribler_utils.tribler_data.torrents
        num_torrents_in_channel = randint(0, len(all_torrents) - 1)
        for i in range(0, num_torrents_in_channel):
            self.torrents.add(tribler_utils.tribler_data.torrents[randint(0, len(all_torrents) - 1)])

    def create_playlist(self, name, description, add_random_torrents=False):
        playlist = Playlist(len(self.playlists) + 1, name, description)

        if add_random_torrents:
            picked_torrents = sample(self.torrents, randint(0, min(20, len(self.torrents))))
            for torrent in picked_torrents:
                playlist.add_torrent(torrent)

        self.playlists.add(playlist)

    def generate_playlist(self):
        num_playlists = randint(1, 5)
        for i in range(num_playlists):
            self.create_playlist("Test playlist %d" % randint(1, 40), "This is a description", add_random_torrents=True)

    def get_json(self):
        return {"id": self.id, "name": self.name, "description": self.description, "votes": self.votes,
                "torrents": len(self.torrents), "spam": self.spam_votes, "modified": self.modified,
                "subscribed": self.subscribed, "dispersy_cid": self.cid, "relevance_score": self.relevance_score,
                "can_edit": self.subscribed}

    def get_playlist_with_id(self, pid):
        for playlist in self.playlists:
            if playlist.id == int(pid):
                return playlist

        return None
