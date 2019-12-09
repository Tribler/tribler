from aiohttp import web

from Tribler.Core.Modules.restapi.rest_endpoint import RESTEndpoint, RESTResponse


class StatisticsEndpoint(RESTEndpoint):
    """
    This endpoint is responsible for handing requests regarding statistics in Tribler.
    """

    def setup_routes(self):
        self.app.add_routes([web.get('/tribler', self.get_tribler_stats),
                             web.get('/ipv8', self.get_ipv8_stats)])

    async def get_tribler_stats(self, request):
        """
        .. http:get:: /statistics/tribler

        A GET request to this endpoint returns general statistics in Tribler.
        The size of the Tribler database is in bytes.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/statistics/tribler

            **Example response**:

            .. sourcecode:: javascript

                {
                    "tribler_statistics": {
                        "num_channels": 1234,
                        "database_size": 384923,
                        "torrent_queue_stats": [{
                            "failed": 2,
                            "total": 9,
                            "type": "TFTP",
                            "pending": 1,
                            "success": 6
                        }, ...]
                    }
                }
        """
        return RESTResponse({'tribler_statistics': self.session.get_tribler_statistics()})

    async def get_ipv8_stats(self, request):
        """
        .. http:get:: /statistics/ipv8

        A GET request to this endpoint returns general statistics of IPv8.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/statistics/ipv8

            **Example response**:

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
