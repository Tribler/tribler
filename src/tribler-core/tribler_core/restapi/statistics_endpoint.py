from aiohttp import web

from aiohttp_apispec import docs

from ipv8.REST.schema import schema

from marshmallow.fields import Integer, String

from tribler_core.restapi.rest_endpoint import RESTEndpoint, RESTResponse


class StatisticsEndpoint(RESTEndpoint):
    """
    This endpoint is responsible for handing requests regarding statistics in Tribler.
    """

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
        return RESTResponse({'tribler_statistics': self.session.get_tribler_statistics()})

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
        return RESTResponse({
            'ipv8_statistics': self.session.get_ipv8_statistics()
        })
