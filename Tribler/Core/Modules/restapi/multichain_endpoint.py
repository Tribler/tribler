"""
Handle HTTP requests for the trust display, whilst validating the arguments and using them in the query.
"""
import json
from binascii import hexlify, unhexlify

from twisted.web import http, resource

from Tribler.Core.exceptions import OperationNotEnabledByConfigurationException
from Tribler.community.multichain.community import MultiChainCommunity


class MultichainEndpoint(resource.Resource):
    """
    This endpoint is responsible for handing requests for multichain data.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)

        child_handler_dict = {"blocks": MultichainBlocksEndpoint, "network": MultichainNetworkEndpoint,
                              "statistics": MultichainStatsEndpoint}

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


class MultichainNetworkEndpoint(resource.Resource):
    """
    Handle HTTP requests for the trust display.
    """

    def __init__(self, session):
        """
        Initialize the MultichainNetworkEndpoint and make a session an attribute from the instance.

        :param session: the Session object where the aggregated data can be retrieved from
        """
        resource.Resource.__init__(self)
        self.session = session


    @staticmethod
    def return_error(request, status_code=http.BAD_REQUEST, message="your request seems to be wrong"):
        """
        Return a HTTP Code 400 with the given message.

        :param request: the request which has to be changed
        :param status_code: the HTTP status code to be returned
        :param message: the error message which is used in the JSON string
        :return: the error message formatted in JSON
        """
        request.setResponseCode(status_code)
        return json.dumps({"error": message})

    def get_multi_chain_community(self):
        """
        Get the MultiChain Community from the session.

        :raise: OperationNotEnabledByConfigurationException if the MultiChain Community cannot be found
        :return: the MultiChain community
        """
        if not self.session.lm.session.get_enable_multichain():
            raise OperationNotEnabledByConfigurationException("multichain is not enabled")
        for community in self.session.get_dispersy_instance().get_communities():
            if isinstance(community, MultiChainCommunity):
                return community

    def render_GET(self, request):
        """
        Process the GET request which retrieves information about the MultiChain network.

        .. http:get:: /multichain/network?dataset=(string: dataset)&focus_node=(string: public key)
                                                                    &neighbor_level=(int: neighbor level)

        A GET request to this endpoint returns the data from the multichain. This data is retrieved from the multichain
        database and will be focused around the given focus node. The neighbor_level parameter specifies which nodes
        are taken into consideration (e.g. a neighbor_level of 2 indicates that only the focus node, it's neighbors
        and the neighbors of those neighbors are taken into consideration).

        Note: the parameters are handled as follows:
        - dataset
            - Not given: MultiChain data
            - "static": Static dummy data
            - "random": Random dummy data
            - otherwise: MultiChain data
        - focus_node
            - Not given: HTTP 400
            - Non-String value: HTTP 400
            - "self": MultiChain Community public key
            - otherwise: Passed data, albeit a string
        - neighbor_level
            - Not given: 1
            - Non-Integer value: 1
            - otherwise: Passed data, albeit an integer

        The returned data will be in such format that the GUI component which visualizes this data can easily use it.
        Although this data might not seem as formatted in a useful way to the human eye, this is done to accommodate as
        little parsing effort at the GUI side.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/multichain/network?dataset=static&focus_node=xyz&neighbor_level=1

            **Example response**:

            .. sourcecode:: javascript

                {
                    "focus_node": "xyz",
                    "neighbor_level": 1,
                    "nodes": [{
                        "public_key": "xyz",
                        "total_up": 12736457,
                        "total_down": 1827364,
                        "page_rank": 0.5
                    }, ...],
                    "edges": [{
                        "from": "xyz",
                        "to": "xyz_n1",
                        "amount": 12384
                    }, ...]
                }

        :param request: the HTTP GET request which specifies the focus node and optionally the neighbor level
        :return: the node data formatted in JSON
        """
        # This header is needed because this request is not made from the same host
        request.setHeader('Access-Control-Allow-Origin', '*')

        if "dataset" in request.args and not (len(request.args["dataset"]) < 1 or len(request.args["dataset"][0]) == 0):
            dataset = request.args["dataset"][0]
            if isinstance(dataset, basestring):
                if dataset == "static":
                    self.get_multi_chain_community().persistence.use_dummy_data(use_random=False)
                elif dataset == "random":
                    self.get_multi_chain_community().persistence.use_dummy_data(use_random=True)

        if "focus_node" not in request.args:
            return MultichainNetworkEndpoint.return_error(request, message="focus_node parameter missing")

        if len(request.args["focus_node"]) < 1 or len(request.args["focus_node"][0]) == 0:
            return MultichainNetworkEndpoint.return_error(request, message="focus_node parameter empty")

        focus_node = request.args["focus_node"][0]
        if isinstance(focus_node, basestring):
            if request.args["focus_node"][0] == "self":
                try:
                    if self.get_multi_chain_community().persistence.dummy_setup:
                        focus_node = "00"
                    else:
                        mc_community = self.get_multi_chain_community()
                        focus_node = hexlify(mc_community.my_member.public_key)
                except OperationNotEnabledByConfigurationException as exc:
                    return MultichainNetworkEndpoint.return_error(request, status_code=http.NOT_FOUND, message=exc.args)
            else:
                focus_node = request.args["focus_node"][0]
        else:
            return MultichainNetworkEndpoint.return_error(request, message="focus_node was not a string")

        neighbor_level = 1
        # Note that isdigit() checks if all chars are numbers, hence negative numbers are not possible to be set
        if "neighbor_level" in request.args and len(request.args["neighbor_level"]) > 0 and \
                request.args["neighbor_level"][0].isdigit():
            neighbor_level = int(request.args["neighbor_level"][0])

        mc_community = self.get_multi_chain_community()
        nodes, edges = mc_community.get_graph(unhexlify(focus_node), neighbor_level)
        return json.dumps({"focus_node": focus_node,
                           "neighbor_level": neighbor_level,
                           "nodes": nodes,
                           "edges": edges})
