import base64
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

            .. sourcecode:: javascript

                {
                    "statistics":
                    {
                        "self_id": "TGliTmFDTFBLO...VGbxS406vrI=",
                        "latest_block_insert_time": "2016-08-04 12:01:53",
                        "self_total_blocks": 8537,
                        "latest_block_id": "Sv03SmkiuL+F4NWxHYdeB6PQeQa/p74EEVQoOVuSz+k=",
                        "latest_block_requester_id": "TGliTmFDTFBLO...nDwlVIk69tc=",
                        "latest_block_up_mb": "19",
                        "self_total_down_mb": 108904,
                        "latest_block_down_mb": "0",
                        "self_total_up_mb": 95138,
                        "latest_block_responder_id": "TGliTmFDTFBLO...VGbxS406vrI="
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

                curl -X GET http://localhost:8085/multichain/blocks/TGliTmFDTFBLOVGbxS406vrI=?limit=10

            **Example response**:

            .. sourcecode:: javascript

                {
                    "blocks": [{
                        "is_requester": True,
                        "up": 123,
                        "down": 495,
                        "total_up_requester": 8393,
                        "total_down_responder": 8943,
                        "sequence_number_requester": 43,
                        "sequence_number_responder": 96,
                        "db_insert_time": 34893242,
                    }, ...]
                }
        """
        mc_community = self.get_multichain_community()
        if not mc_community:
            request.setResponseCode(http.NOT_FOUND)
            return json.dumps({"error": "multichain community not found"})

        limit_blocks = 100

        if 'limit' in request.args and len(request.args['limit']) > 0:
            limit_blocks = int(request.args['limit'][0])

        blocks = mc_community.persistence.get_blocks(base64.decodestring(self.identity), limit_blocks)
        return json.dumps({"blocks": [block.to_dictionary() for block in blocks]})
