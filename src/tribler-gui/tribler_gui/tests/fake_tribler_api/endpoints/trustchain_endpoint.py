from random import randint

from aiohttp import web

from tribler_core.restapi.rest_endpoint import RESTEndpoint, RESTResponse
from tribler_core.utilities.unicode import hexlify

from tribler_gui.tests.fake_tribler_api import tribler_utils


class TrustchainEndpoint(RESTEndpoint):
    def setup_routes(self):
        self.app.add_routes([web.get('/statistics', self.get_statistics)])

    async def get_statistics(self, _):
        last_block = tribler_utils.tribler_data.trustchain_blocks[-1]

        return RESTResponse(
            {
                'statistics': {
                    "id": hexlify(b'a' * 20),
                    "total_blocks": len(tribler_utils.tribler_data.trustchain_blocks),
                    "total_down": last_block.total_down,
                    "total_up": last_block.total_up,
                    "peers_that_pk_helped": randint(10, 50),
                    "peers_that_helped_pk": randint(10, 50),
                    "latest_block": last_block.to_dictionary(),
                }
            }
        )
