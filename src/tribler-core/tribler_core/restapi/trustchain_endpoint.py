from aiohttp import web

from aiohttp_apispec import docs

from ipv8.REST.schema import schema

from marshmallow.fields import Integer, String

from tribler_core.restapi.rest_endpoint import HTTP_NOT_FOUND, RESTEndpoint, RESTResponse
from tribler_core.utilities.unicode import recursive_unicode


class TrustchainEndpoint(RESTEndpoint):
    """
    This endpoint is responsible for handing requests for trustchain data.
    """

    def setup_routes(self):
        self.app.add_routes([web.get('/statistics', self.get_statistics)])

    @docs(
        tags=["TrustChain"],
        summary="Return statistics about the trustchain community.",
        responses={
            200: {
                "schema": schema(TrustchainStatisticsResponse={
                    'statistics': schema(TrustchainStatistics={
                        'id': String,
                        'peers_that_pk_helped': Integer,
                        'peers_that_helped_pk': Integer,
                        'total_blocks': Integer,
                        'total_down': Integer,
                        'total_up': Integer
                    })
                })
            }
        }
    )
    async def get_statistics(self, request):
        if 'MB' not in self.session.wallets:
            return RESTResponse({"error": "TrustChain community not found"}, status=HTTP_NOT_FOUND)
        return RESTResponse({'statistics': recursive_unicode(self.session.wallets['MB'].get_statistics())})
