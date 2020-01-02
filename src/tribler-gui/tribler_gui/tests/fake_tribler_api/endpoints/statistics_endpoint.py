from random import randint

from aiohttp import web

from tribler_core.restapi.rest_endpoint import RESTEndpoint, RESTResponse


class StatisticsEndpoint(RESTEndpoint):
    """
    This endpoint is responsible for handing requests regarding statistics in Tribler.
    """

    def setup_routes(self):
        self.app.add_routes([web.get('/tribler', self.get_tribler_stats), web.get('/ipv8', self.get_ipv8_stats)])

    async def get_tribler_stats(self, _request):
        return RESTResponse(
            {
                'tribler_statistics': {
                    "db_size": randint(1000, 1000000),
                    "num_channels": randint(1, 100),
                    "num_torrents": randint(1000, 10000),
                }
            }
        )

    async def get_ipv8_stats(self, _request):
        return RESTResponse({'ipv8_statistics': {"total_up": 13423, "total_down": 3252}})
