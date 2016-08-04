import json

from twisted.web import http, resource

from Tribler.community.multichain.community import MultiChainCommunity


class MultichainEndpoint(resource.Resource):
    """
    This endpoint is responsible for handing requests for multichain data.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)

        child_handler_dict = {"stats": MultichainStatsEndpoint}

        for path, child_cls in child_handler_dict.iteritems():
            self.putChild(path, child_cls(session))


class MultichainStatsEndpoint(resource.Resource):
    """
    This class handles requests regarding the tunnel community debug information.
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
        .. http:get:: /multichain/stats

        A GET request to this endpoint returns statistics about the multichain community

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/multichain/stats

            **Example response**:

            .. sourcecode:: javascript

                {
                  "stats":
                  {
                    "self_id": "Xf/gH2J7+BBAg=",
                    "self_total_blocks": 42,
                    "self_total_up_mb": 42,
                    "self_total_down_mb": 42,
                    "latest_block_insert_time": "2016-08-04 12:29:00",
                    "latest_block_id": "KYbEe/gH2J7+BBTtg=",
                    "latest_block_requester_id": "Xf/gH2J7+BBAg=",
                    "latest_block_responder_id": "some+base64+string==",
                    "latest_block_up_mb": "42",
                    "latest_block_down_mb": "42"
                  }
                }
        """
        mc_community = self.get_multichain_community()
        if not mc_community:
            request.setResponseCode(http.NOT_FOUND)
            return json.dumps({"error": "multichain community not found"})

        return json.dumps({'stats': mc_community.get_statistics()})
