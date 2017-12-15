import json

from twisted.web import http, resource

from Tribler.community.triblerchain.community import TriblerChainCommunity


class TrustchainEndpoint(resource.Resource):
    """
    This endpoint is responsible for handing requests for trustchain data.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)

        child_handler_dict = {
            "statistics": TrustchainStatsEndpoint, 
            "blocks": TrustchainBlocksEndpoint,
            "bootstrap" : TrustchainBootstrapEndpoint}

        for path, child_cls in child_handler_dict.iteritems():
            self.putChild(path, child_cls(session))


class TrustchainBaseEndpoint(resource.Resource):
    """
    This class represents the base class of the trustchain community.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

    def get_trustchain_community(self):
        """
        Search for the trustchain community in the dispersy communities.
        """
        for community in self.session.get_dispersy_instance().get_communities():
            if isinstance(community, TriblerChainCommunity):
                return community
        return None


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
        mc_community = self.get_trustchain_community()
        if not mc_community:
            request.setResponseCode(http.NOT_FOUND)
            return json.dumps({"error": "trustchain community not found"})

        return json.dumps({'statistics': mc_community.get_statistics()})


class TrustchainBlocksEndpoint(TrustchainBaseEndpoint):
    """
    This class handles requests regarding the trustchain community blocks.
    """

    def getChild(self, path, request):
        return TrustchainBlocksIdentityEndpoint(self.session, path)


class TrustchainBlocksIdentityEndpoint(TrustchainBaseEndpoint):
    """
    This class represents requests for blocks of a specific identity.
    """

    def __init__(self, session, identity):
        TrustchainBaseEndpoint.__init__(self, session)
        self.identity = identity

    def render_GET(self, request):
        """
        .. http:get:: /trustchain/blocks/TGliTmFDTFBLOVGbxS406vrI=?limit=(int: max nr of returned blocks)

        A GET request to this endpoint returns all blocks of a specific identity, both that were signed and responded
        by him. You can optionally limit the amount of blocks returned, this will only return some of the most recent
        blocks.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/trustchain/blocks/d78130e71bdd1...=?limit=10

            **Example response**:

            .. sourcecode:: javascript

                {
                    "blocks": [{
                        "hash": ab672fd6acc0...
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
                    }, ...]
                }
        """
        mc_community = self.get_trustchain_community()
        if not mc_community:
            request.setResponseCode(http.NOT_FOUND)
            return json.dumps({"error": "trustchain community not found"})

        limit_blocks = 100

        if 'limit' in request.args:
            try:
                limit_blocks = int(request.args['limit'][0])
            except ValueError:
                limit_blocks = -1

        if limit_blocks < 1 or limit_blocks > 1000:
            request.setResponseCode(http.BAD_REQUEST)
            return json.dumps({"error": "limit parameter out of range"})

        blocks = mc_community.persistence.get_latest_blocks(self.identity.decode("HEX"), limit_blocks)
        return json.dumps({"blocks": [dict(block) for block in blocks]})



class TrustchainBootstrapEndpoint(TrustchainBaseEndpoint):
    """
    Bootstrap a new identity and transfer some reputation to the new key.
    """

    def render_GET(self, request):
        """
        .. http:get:: /trustchain/bootstrap?up=int&down=int

        A GET request to this endpoint generates a new identity and transfers some reputation to it.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/trustchain/bootstrap?up=100000&down=40000

            **Example response**:

            .. sourcecode:: javascript

                {
                    "private_key" : "NEW_KEY",
                    "public_key"  : "NEW_PUBLIC_KEY" ,
                     "transactions" : [
                         {
                            "hash": "ab672fd6acc0",
                            "tx" : {
                                "up": 100000,
                                "down": 40000,
                                "total_up": 100000,
                                "total_down": 40000,
                            },
                            "sequence_number": 0,
                            "link_public_key": "PC_KEY",
                            "link_sequence_number": 1210,
                            "previous_hash": 00000000
                        }
                    ]
                    }
        """
        mc_community = self.get_trustchain_community()
        if not mc_community:
            request.setResponseCode(http.NOT_FOUND)
            return json.dumps({"error": "trustchain community not found"})

        up = 100000000
        down = 1000
        if 'up' in request.args:
            try:
                up = int(request.args['up'][0])
            except ValueError:
                up = up
                
        if 'down' in request.args:
            try:
                down = int(request.args['down'][0])
            except ValueError:
                down = down

        return json.dumps(  {
                    "private_key" : "NEW_KEY",
                    "public_key"  : "NEW_PUBLIC_KEY" ,
                     "transactions" : [
                         {
                            "hash": "ab672fd6acc0",
                            "tx" : {
                                "up": up,
                                "down": down,
                                "total_up": up,
                                "total_down": down,
                            },
                            "sequence_number": 0,
                            "link_public_key": "PC_KEY",
                            "link_sequence_number": 1210,
                            "previous_hash": 00000000
                        }
                    ]
               
                    })

