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
            json_torrent = torrent.get_json()
            json_torrent['added'] = randint(1065904348, 1465904348)
            response_torrents.append(json_torrent)
        return json.dumps({"torrents": response_torrents})
