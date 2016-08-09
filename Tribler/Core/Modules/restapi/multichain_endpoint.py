import json

from twisted.web import http, resource

from Tribler.community.multichain.community import MultiChainCommunity


class MultichainEndpoint(resource.Resource):
    """
    This endpoint is responsible for handing requests for multichain data.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)

        child_handler_dict = {"statistics": MultichainStatsEndpoint}

        for path, child_cls in child_handler_dict.iteritems():
            self.putChild(path, child_cls(session))


class MultichainStatsEndpoint(resource.Resource):
    """
    This class handles requests regarding the multichain community information.
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
