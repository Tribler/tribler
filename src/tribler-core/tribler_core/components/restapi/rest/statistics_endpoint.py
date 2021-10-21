from aiohttp import web

from aiohttp_apispec import docs

from ipv8.REST.schema import schema

from marshmallow.fields import Integer, String

from tribler_core.components.restapi.rest.rest_endpoint import RESTEndpoint, RESTResponse
from tribler_core.utilities.utilities import froze_it


@froze_it
class StatisticsEndpoint(RESTEndpoint):
    """
    This endpoint is responsible for handing requests regarding statistics in Tribler.
    """

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.mds = None
        self.ipv8 = None

    def setup_routes(self):
        self.app.add_routes([web.get('/tribler', self.get_tribler_stats),
                             web.get('/ipv8', self.get_ipv8_stats)])

    @docs(
        tags=["General"],
        summary="Return general statistics of Tribler.",
        responses={
            200: {
                "schema": schema(TriblerStatisticsResponse={
                    'statistics': schema(TriblerStatistics={
                        'num_channels': Integer,
                        'database_size': Integer,
                        'torrent_queue_stats': [
                            schema(TorrentQueueStats={
                                'failed': Integer,
                                'total': Integer,
                                'type': String,
                                'pending': Integer,
                                'success': Integer
                            })
                        ],
                    })
                })
            }
        }
    )
    async def get_tribler_stats(self, request):
        stats_dict = {}
        if self.mds:
            db_size = self.mds.get_db_file_size()
            stats_dict = {"db_size": db_size,
                          "num_channels": self.mds.get_num_channels(),
                          "num_torrents": self.mds.get_num_torrents()}

        return RESTResponse({'tribler_statistics': stats_dict})

    @docs(
        tags=["General"],
        summary="Return general statistics of IPv8.",
        responses={
            200: {
                "schema": schema(IPv8StatisticsResponse={
                    'statistics': schema(IPv8Statistics={
                        'total_up': Integer,
                        'total_down': Integer
                    })
                })
            }
        }
    )
    async def get_ipv8_stats(self, request):
        """

            .. sourcecode:: javascript

                {
                    "ipv8_statistics": {
                        "total_up": 3424324,
                        "total_down": 859484
                    }
                }
        """
        stats_dict = {}
        if self.ipv8:
            stats_dict = {
                "total_up": self.ipv8.endpoint.bytes_up,
                "total_down": self.ipv8.endpoint.bytes_down,
                # "session_uptime": time.time() - self.ipv8_start_time
            }
        return RESTResponse({'ipv8_statistics': stats_dict})
