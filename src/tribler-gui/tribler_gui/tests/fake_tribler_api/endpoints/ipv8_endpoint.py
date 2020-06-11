from random import choice, randint

from aiohttp import web

from tribler_core.restapi.rest_endpoint import RESTEndpoint, RESTResponse

from tribler_gui.tests.fake_tribler_api import tribler_utils


class IPv8Endpoint(RESTEndpoint):
    def setup_routes(self):
        self.app.add_routes(
            [
                web.get('/trustchain/users/{public_key}/blocks', self.get_blocks),
                web.get('/tunnel/circuits', self.get_circuits),
                web.get('/tunnel/relays', self.get_relays),
                web.get('/tunnel/exits', self.get_exits),
                web.get('/dht/statistics', self.get_dht_stats),
                web.get('/dht/buckets', self.get_dht_buckets),
                web.get('/overlays', self.get_overlays),
            ]
        )

    async def get_blocks(self, _):
        return RESTResponse(
            {"blocks": [block.to_dictionary() for block in tribler_utils.tribler_data.trustchain_blocks]}
        )

    async def get_circuits(self, _):
        return RESTResponse(
            {"circuits": [circuit.to_dictionary() for circuit in tribler_utils.tribler_data.tunnel_circuits]}
        )

    async def get_relays(self, _request):
        return RESTResponse({"relays": [relay.to_dictionary() for relay in tribler_utils.tribler_data.tunnel_relays]})

    async def get_exits(self, _):
        return RESTResponse(
            {"exits": [exit_socket.to_dictionary() for exit_socket in tribler_utils.tribler_data.tunnel_exits]}
        )

    async def get_dht_stats(self, _):
        return RESTResponse({"statistics": tribler_utils.tribler_data.dht_stats})

    async def get_dht_buckets(self, _):
        return RESTResponse({"buckets": tribler_utils.tribler_data.dht_buckets})

    async def get_overlays(self, _):
        return RESTResponse(
            {
                'overlays': [
                    {
                        "master_peer": ''.join(choice('0123456789abcdef') for _ in range(20)),
                        "my_peer": ''.join(choice('0123456789abcdef') for _ in range(20)),
                        "global_time": randint(1, 10000),
                        "peers": [],
                        "overlay_name": "TestOverlay",
                    }
                ]
            }
        )
