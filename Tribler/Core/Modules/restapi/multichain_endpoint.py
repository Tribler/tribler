import json
from twisted.web import http, resource

from Tribler.community.multichain.community import MultiChainCommunity


class MultichainEndpoint(resource.Resource):
    """
    This endpoint is responsible for handing requests for multichain data.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)

        child_handler_dict = {"statistics": MultichainStatsEndpoint, "blocks": MultichainBlocksEndpoint}

        for path, child_cls in child_handler_dict.iteritems():
            self.putChild(path, child_cls(session))


class MultichainBaseEndpoint(resource.Resource):
    """
    This class represents the base class of the multichain community.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

    def get_multichain_community(self):
        """
        Search for the multichain community in the dispersy communities.
        """
        for community in self.session.get_dispersy_instance().get_communities():
            if isinstance(community, MultiChainCommunity):
                return community
        return None


class MultichainStatsEndpoint(MultichainBaseEndpoint):
    """
    This class handles requests regarding the multichain community information.
    """

    def render_GET(self, request):
        """
        .. http:get:: /multichain/statistics

        A GET request to this endpoint returns statistics about the multichain community

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/multichain/statistics

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
                            "hash": ab672fd6acc0...
                            "up": 123,
                            "down": 495,
                            "total_up": 8393,
                            "total_down": 8943,
                            "link_public_key": 7324b765a98e,
                            "sequence_number": 50,
                            "link_public_key": 9a5572ec59bbf,
                            "link_sequence_number": 3482,
                            "previous_hash": bd7830e7bdd1...,
                        }
                    }
                }
        """
        mc_community = self.get_multichain_community()
        if not mc_community:
            request.setResponseCode(http.NOT_FOUND)
            return json.dumps({"error": "multichain community not found"})

        return json.dumps({'statistics': mc_community.get_statistics()})


class MultichainBlocksEndpoint(MultichainBaseEndpoint):
    """
    This class handles requests regarding the multichain community blocks.
    """

    def getChild(self, path, request):
        return MultichainBlocksIdentityEndpoint(self.session, path)


class MultichainBlocksIdentityEndpoint(MultichainBaseEndpoint):
    """
    This class represents requests for blocks of a specific identity.
    """

    def __init__(self, session, identity):
        MultichainBaseEndpoint.__init__(self, session)
        self.identity = identity

    def render_GET(self, request):
        """
        .. http:get:: /multichain/blocks/TGliTmFDTFBLOVGbxS406vrI=?limit=(int: max nr of returned blocks)

        A GET request to this endpoint returns all blocks of a specific identity, both that were signed and responded
        by him. You can optionally limit the amount of blocks returned, this will only return some of the most recent
        blocks.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/multichain/blocks/d78130e71bdd1...=?limit=10

            **Example response**:

            .. sourcecode:: javascript

                {
                    "blocks": [{
                        "hash": ab672fd6acc0...
                        "up": 123,
                        "down": 495,
                        "total_up": 8393,
                        "total_down": 8943,
                        "sequence_number": 50,
                        "link_public_key": 9a5572ec59bbf,
                        "link_sequence_number": 3482,
                        "previous_hash": bd7830e7bdd1...,
                    }, ...]
                }
        """
        mc_community = self.get_multichain_community()
        if not mc_community:
            request.setResponseCode(http.NOT_FOUND)
            return json.dumps({"error": "multichain community not found"})

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
