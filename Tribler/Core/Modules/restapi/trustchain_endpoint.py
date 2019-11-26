from aiohttp import web

from Tribler.Core.Modules.restapi.rest_endpoint import HTTP_BAD_REQUEST, HTTP_NOT_FOUND, RESTEndpoint, RESTResponse
from Tribler.Core.Utilities.unicode import recursive_unicode


class TrustchainEndpoint(RESTEndpoint):
    """
    This endpoint is responsible for handing requests for trustchain data.
    """

    def setup_routes(self):
        self.app.add_routes([web.get('/statistics', self.get_statistics),
                             web.get('/bootstrap', self.bootstrap)])

    async def get_statistics(self, request):
        """
        .. http:get:: /trustchain/statistics

        A GET request to this endpoint returns statistics about the trustchain community

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/trustchain/statistics

            **Example response**:

            Note: latest_block does not exist if there is no data

            .. sourcecode:: javascript

                {
                    "statistics":
                    {
                        "id": "TGliTmFDTFBLO...VGbxS406vrI=",
                        "total_blocks": 8537,
                        "total_down": 108904042,
                        "total_up": 95138354,
                        "latest_block":
                        {
                            "hash": ab672fd6acc0...,
                            "link_public_key": 7324b765a98e,
                            "sequence_number": 50,
                            "link_public_key": 9a5572ec59bbf,
                            "link_sequence_number": 3482,
                            "previous_hash": bd7830e7bdd1...,
                            "transaction": {
                                "up": 123,
                                "down": 495,
                                "total_up": 8393,
                                "total_down": 8943,
                            }
                        }
                    }
                }
        """
        if 'MB' not in self.session.lm.wallets:
            return RESTResponse({"error": "TrustChain community not found"}, status=HTTP_NOT_FOUND)
        return RESTResponse({'statistics': recursive_unicode(self.session.lm.wallets['MB'].get_statistics())})

    async def bootstrap(self, request):
        """
        .. http:get:: /trustchain/bootstrap?amount=int

        A GET request to this endpoint generates a new identity and transfers bandwidth tokens to it.
        The amount specifies how much tokens need to be emptied into the new identity

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/trustchain/bootstrap?amount=1000

            **Example response**:

            .. sourcecode:: javascript

                {
                    "private_key": "TGliTmFDTFNLOmC4BR7otCpn+NzTBAFwKdSJdpT0KG9Zy5vPGX6s3rDXmNiDoGKyToLeYYB88vj9Rj5NW
                                    pbNf/ldcixYZ2YxQ7Q=",
                    "transaction": {
                        "down": 0,
                        "up": 1000
                    },
                    "block": {
                        "block_hash": "THJxNlKWMQG1Tio+Yz5CUCrnWahcyk6TDVfRLQf7w6M=",
                        "sequence_number": 1
                    }
                }
        """

        if 'MB' not in self.session.lm.wallets:
            return RESTResponse({"error": "bandwidth wallet not found"}, status=HTTP_NOT_FOUND)
        bandwidth_wallet = self.session.lm.wallets['MB']

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
