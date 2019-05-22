from __future__ import absolute_import

from twisted.web import http, resource

import Tribler.Core.Utilities.json_util as json
from Tribler.Core.Utilities.unicode import recursive_unicode


class TrustchainEndpoint(resource.Resource):
    """
    This endpoint is responsible for handing requests for trustchain data.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)

        child_handler_dict = {
            b"statistics": TrustchainStatsEndpoint,
            b"bootstrap": TrustchainBootstrapEndpoint
        }

        for path, child_cls in child_handler_dict.items():
            self.putChild(path, child_cls(session))


class TrustchainBaseEndpoint(resource.Resource):
    """
    This class represents the base class of the trustchain community.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session


class TrustchainStatsEndpoint(TrustchainBaseEndpoint):
    """
    This class handles requests regarding the trustchain community information.
    """

    def render_GET(self, request):
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
            request.setResponseCode(http.NOT_FOUND)
            return json.twisted_dumps({"error": "TrustChain community not found"})

        return json.twisted_dumps({'statistics': self.session.lm.wallets['MB'].get_statistics()})


class TrustchainBootstrapEndpoint(TrustchainBaseEndpoint):
    """
    Bootstrap a new identity and transfer some bandwidth tokens to the new key.
    """

    def render_GET(self, request):
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
            request.setResponseCode(http.NOT_FOUND)
            return json.twisted_dumps({"error": "bandwidth wallet not found"})
        bandwidth_wallet = self.session.lm.wallets['MB']

        available_tokens = bandwidth_wallet.get_bandwidth_tokens()

        args = recursive_unicode(request.args)
        if 'amount' in args:
            try:
                amount = int(args['amount'][0])
            except ValueError:
                request.setResponseCode(http.BAD_REQUEST)
                return json.twisted_dumps({"error": "Provided token amount is not a number"})

            if amount <= 0:
                request.setResponseCode(http.BAD_REQUEST)
                return json.twisted_dumps({"error": "Provided token amount is zero or negative"})
        else:
            amount = available_tokens

        if amount <= 0 or amount > available_tokens:
            request.setResponseCode(http.BAD_REQUEST)
            return json.twisted_dumps({"error": "Not enough bandwidth tokens available"})

        result = bandwidth_wallet.bootstrap_new_identity(amount)
        result['private_key'] = result['private_key'].decode('utf-8')
        result['block']['block_hash'] = result['block']['block_hash'].decode('utf-8')
        return json.twisted_dumps(result)
