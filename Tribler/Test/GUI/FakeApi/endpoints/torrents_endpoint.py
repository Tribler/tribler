import json
from random import sample, randint

from twisted.web import resource

import tribler_utils


class TorrentsEndpoint(resource.Resource):

    def __init__(self):
        resource.Resource.__init__(self)
        self.putChild("random", TorrentsRandomEndpoint())


class TorrentsRandomEndpoint(resource.Resource):

    def render_GET(self, request):
        rand_torrents = sample(tribler_utils.tribler_data.torrents, 20)
        response_torrents = []
        for torrent in rand_torrents:
            torrent_json = torrent.get_json()
            if tribler_utils.tribler_data.settings["settings"]["general"]["family_filter"] and torrent_json["category"] == 'xxx':
                continue

            response_torrents.append(torrent_json)
        return json.dumps({"torrents": response_torrents})
