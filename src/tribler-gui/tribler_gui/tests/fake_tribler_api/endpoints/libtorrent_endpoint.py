from aiohttp import web

from tribler_core.restapi.rest_endpoint import RESTEndpoint, RESTResponse


class LibTorrentEndpoint(RESTEndpoint):

    def setup_routes(self):
        self.app.add_routes([web.get('/settings', self.get_settings),
                             web.get('/session', self.get_session)])

    async def get_settings(self, _request):
        return RESTResponse({
            "hop": 0,
            "settings": {
                "urlseed_wait_retry": 30,
                "enable_upnp": True,
                "send_socket_buffer_size": 0,
                "lock_disk_cache": False,
                "i2p_port": 0
            }
        })

    async def get_session(self, _request):
        return RESTResponse({
            "hop": 0,
            "session": {
                "peer.num_peers_end_game": 0,
                "utp.utp_timeout": 2,
                "dht.dht_put_out": 0,
                "peer.choked_piece_requests": 0,
                "ses.num_incoming_allowed_fast": 0
            }
        })
