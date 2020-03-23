from aiohttp import web

from aiohttp_apispec import docs

from ipv8.REST.schema import schema

from marshmallow.fields import Integer, String

from tribler_core.restapi.rest_endpoint import HTTP_BAD_REQUEST, HTTP_NOT_FOUND, RESTEndpoint, RESTResponse
from tribler_core.utilities.unicode import recursive_unicode


class TrustchainEndpoint(RESTEndpoint):
    """
    This endpoint is responsible for handing requests for trustchain data.
    """

    def setup_routes(self):
        self.app.add_routes([web.get('/statistics', self.get_statistics),
                             web.get('/bootstrap', self.bootstrap)])

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

    @docs(
        tags=["TrustChain"],
        summary="Generate a new identity and transfers bandwidth tokens to it..",
        parameters=[{
            'in': 'query',
            'name': 'amount',
            'description': 'Specifies how much tokens need to be emptied into the new identity',
            'type': 'integer',
            'required': True
        }],
        responses={
            200: {
                "schema": schema(TrustchainBootstrapResponse={
                    'private_key': String,
                    'transaction': schema(BootstrapTransaction={
                        'down': Integer,
                        'up': Integer
                    }),
                    'block': schema(BootstrapBlock={
                        'block_hash': String,
                        'sequence_number': String
                    })
                })
            }
        }
    )
    async def bootstrap(self, request):
        if 'MB' not in self.session.wallets:
            return RESTResponse({"error": "bandwidth wallet not found"}, status=HTTP_NOT_FOUND)
        bandwidth_wallet = self.session.wallets['MB']

        available_tokens = bandwidth_wallet.get_bandwidth_tokens()

        args = request.query
        if 'amount' in args:
            try:
                amount = int(args['amount'])
            except ValueError:
                return RESTResponse({"error": "Provided token amount is not a number"}, status=HTTP_BAD_REQUEST)

            if amount <= 0:
                return RESTResponse({"error": "Provided token amount is zero or negative"}, status=HTTP_BAD_REQUEST)
        else:
            amount = available_tokens

        if amount <= 0 or amount > available_tokens:
            return RESTResponse({"error": "Not enough bandwidth tokens available"}, status=HTTP_BAD_REQUEST)

        result = bandwidth_wallet.bootstrap_new_identity(amount)
        result['private_key'] = result['private_key'].decode('utf-8')
        result['block']['block_hash'] = result['block']['block_hash'].decode('utf-8')
        return RESTResponse(result)
