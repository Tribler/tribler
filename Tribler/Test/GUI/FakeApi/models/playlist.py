

class Playlist:

    def __init__(self, id, name, description):
        self.id = id
        self.name = name
        self.description = description
        self.torrents = set()

    def add_torrent(self, torrent):
        self.torrents.add(torrent)

    def get_json(self):
        torrents_json = []
        for torrent in self.torrents:
            torrents_json.append(torrent.get_json())

        return {"id": self.id, "name": self.name, "description": self.description, "torrents": torrents_json}
