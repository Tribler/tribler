from __future__ import absolute_import

from twisted.web import resource

import Tribler.Core.Utilities.json_util as json


class LibTorrentEndpoint(resource.Resource):

    def __init__(self):
        resource.Resource.__init__(self)
        self.putChild(b"settings", LibTorrentSettingsEndpoint())
        self.putChild(b"session", LibTorrentSessionEndpoint())


class LibTorrentSettingsEndpoint(resource.Resource):

    def render_GET(self, _request):
        return json.twisted_dumps({
            "hop": 0,
            "settings": {
                "urlseed_wait_retry": 30,
                "enable_upnp": True,
                "send_socket_buffer_size": 0,
                "lock_disk_cache": False,
                "i2p_port": 0
            }
        })


class LibTorrentSessionEndpoint(resource.Resource):

    def render_GET(self, _request):
        return json.twisted_dumps({
            "hop": 0,
            "session": {
                "peer.num_peers_end_game": 0,
                "utp.utp_timeout": 2,
                "dht.dht_put_out": 0,
                "peer.choked_piece_requests": 0,
                "ses.num_incoming_allowed_fast": 0
            }
        })
