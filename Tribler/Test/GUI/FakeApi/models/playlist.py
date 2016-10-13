import tribler_utils


class Playlist:

    def __init__(self, id, name, description):
        self.id = id
        self.name = name
        self.description = description
        self.torrents = set()

    def add_torrent(self, torrent):
        self.torrents.add(torrent)

    def remove_torrent(self, infohash):
        torrent_to_delete = None
        for torrent in self.torrents:
            if torrent.infohash == infohash:
                torrent_to_delete = torrent
                break
        self.torrents.remove(torrent_to_delete)

    def get_json(self):
        torrents_json = []
        for torrent in self.torrents:
            torrent_json = torrent.get_json()
            if tribler_utils.tribler_data.settings["settings"]["general"]["family_filter"] and torrent_json["category"] == 'xxx':
                continue
            torrents_json.append(torrent_json)

        return {"id": self.id, "name": self.name, "description": self.description, "torrents": torrents_json}
