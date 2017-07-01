"""
Handle HTTP requests for the trust display, whilst validating the arguments and using them in the query.
"""
import json
import sys
from binascii import hexlify

from twisted.web import http, resource
from twisted.web.server import NOT_DONE_YET

from Tribler.Core.exceptions import OperationNotEnabledByConfigurationException
from Tribler.community.triblerchain.community import TriblerChainCommunity


class TrustchainEndpoint(resource.Resource):
    """
    This endpoint is responsible for handing requests for trustchain data.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)

        child_handler_dict = {"blocks": TrustchainBlocksEndpoint, "network": TrustChainNetworkEndpoint,
                              "statistics": TrustchainStatsEndpoint, }

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
        tribler_chain_community = self.get_trustchain_community()
        if not tribler_chain_community:
            request.setResponseCode(http.NOT_FOUND)
            return json.dumps({"error": "trustchain community not found"})

        return json.dumps({'statistics': tribler_chain_community.get_statistics()})


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


class TrustChainNetworkEndpoint(resource.Resource):
    """
    Handle HTTP requests for the trust display.
    """

    def __init__(self, session):
        """
        Create a new TrustChainNetworkEndpoint instance.

        :param session: a Session instance from where the aggregate network data can be retrieved from
        """
        resource.Resource.__init__(self)
        self.session = session

    @staticmethod
    def return_error(request, status_code=http.BAD_REQUEST, message="your request seems to be wrong"):
        """
        Return a HTTP status code with the given error message.

        :param request: the request which has to be changed
        :param status_code: the HTTP status code to be returned
        :param message: the error message which is used in the JSON string
        :return: the error message formatted in JSON
        """
        request.setResponseCode(status_code)
        return json.dumps({"error": message})

    def get_tribler_chain_community(self):
        """
        Get the TriblerChain Community from the session.

        :raise: OperationNotEnabledByConfigurationException if the TrustChain Community cannot be found
        :return: the TriblerChain community
        """
        if not self.session.config.get_trustchain_enabled():
            raise OperationNotEnabledByConfigurationException("trustchain is not enabled")
        for community in self.session.get_dispersy_instance().get_communities():
            if isinstance(community, TriblerChainCommunity):
                return community

    def render_GET(self, request):
        """
        Process the GET request which retrieves information about the TrustChain network.

        .. http:get:: /trustchain/network?focus_node=(string: public key)
                                          &neighbor_level=(int: neighbor level)
                                          &max_neighbors=(int: max_neighbors)
                                          &mandatory_nodes=(list: mandatory_nodes)

        A GET request to this endpoint returns the data from the trustchain. This data is retrieved from the trustchain
        database and will be focused around the given focus node. The neighbor_level parameter specifies which nodes
        are taken into consideration (e.g. a neighbor_level of 2 indicates that only the focus node, it's neighbors
        and the neighbors of those neighbors are taken into consideration).

        Note: the parameters are handled as follows:
        - focus_node
            - Not given: TriblerChain Community public key
            - Non-String value: HTTP 400
            - "self": TriblerChain Community public key
            - otherwise: Passed data, albeit a string
        - neighbor_level
            - Not given: 1
            - Non-Integer value: 1
            - otherwise: Passed data, albeit an integer
        - max_neighbors
            - Not given: 8
            - Non-integer value: 8
            - Negative integer: 8
            - 0: unlimited
            - otherwise: Passed data, albeit an integer
        - mandatory_nodes:
            - Not given: [user_node]
            - otherwise: list of given arguments

        The returned data will be in such format that the GUI component which visualizes this data can easily use it.
        Although this data might not seem as formatted in a useful way to the human eye, this is done to accommodate as
        little parsing effort at the GUI side.

            **Example request**:

            .. sourcecode:: none

                curl -X GET 'http://localhost:8085/trustchain/network?dataset=static&focus_node=xyz&neighbor_level=1
                                                                     &max_neighbors=4&mandatory_neighbors=['xyz']'

            **Example response**:

            .. sourcecode:: javascript

                {
                    "user_node": "abc",
                    "focus_node": "xyz",
                    "neighbor_level": 1,
                    "nodes": [{
                        "public_key": "xyz",
                        "total_up": 12736457,
                        "total_down": 1827364,
                        "score": 0.0011,
                        "total_neighbors": 1
                    }, ...],
                    "edges": [{
                        "from": "xyz",
                        "to": "xyz_n1",
                        "amount": 12384
                    }, ...]
                }

        :param request: the HTTP GET request which specifies the focus node and optionally the neighbor level
        """
        # This header is needed because this request is not made from the same host
        request.setHeader('Access-Control-Allow-Origin', '*')

        try:
            tribler_chain_community = self.get_tribler_chain_community()
        except OperationNotEnabledByConfigurationException as exc:
            return TrustChainNetworkEndpoint.return_error(request, status_code=http.NOT_FOUND, message=exc.args)

        focus_node = "self"
        if "focus_node" in request.args:
            focus_node = request.args["focus_node"][0]

            if not focus_node:
                return TrustChainNetworkEndpoint.return_error(request, message="focus_node parameter empty")

        if focus_node == "self":
            focus_node = hexlify(tribler_chain_community.my_member.public_key)

        user_node = hexlify(tribler_chain_community.my_member.public_key)

        neighbor_level = self.get_neighbor_level(request.args)

        max_neighbors = self.get_max_neighbors(request.args)

        mandatory_nodes = self.get_mandatory_nodes(request.args)

        def finalize_request((nodes, edges)):
            request.write(json.dumps({"user_node": user_node,
                                      "focus_node": focus_node,
                                      "neighbor_level": neighbor_level,
                                      "nodes": nodes,
                                      "edges": edges}))
            request.finish()

        d = tribler_chain_community.get_graph(focus_node, neighbor_level, max_neighbors, mandatory_nodes)
        d.addCallback(finalize_request)

        return NOT_DONE_YET

    @staticmethod
    def get_neighbor_level(arguments):
        """
        Get the neighbor level.

        The default neighbor level is 1.
        :param arguments: the arguments supplied with the HTTP request
        :return: the neighbor level
        """
        neighbor_level = 1
        # Note that isdigit() checks if all chars are numbers, hence negative numbers are not possible to be set
        if "neighbor_level" in arguments and arguments["neighbor_level"][0].isdigit():
            neighbor_level = int(arguments["neighbor_level"][0])
        return neighbor_level

    @staticmethod
    def get_max_neighbors(arguments):
        """
        Get the maximum amount of higher level neighbors for one node.

        The default maximum is unlimited (portrayed by sys.maxint).
        :param arguments: the arguments supplied with the HTTP request
        :return: maximal number of higher level neighbors per node
        """
        max_neighbors = 0
        # Note that isdigit() checks if all chars are numbers, hence negative numbers are not possible to be set
        if "max_neighbors" in arguments and arguments["max_neighbors"][0].isdigit():
            max_neighbors = int(arguments["max_neighbors"][0])
        return max_neighbors or sys.maxint

    @staticmethod
    def get_mandatory_nodes(arguments):
        """
        Get the list of mandatory nodes.

        The default is [user_node].
        :param arguments: the arguments supplied with the HTTP request
        :return: list of mandatory nodes
        """
        mandatory_nodes = []
        if "mandatory_nodes" in arguments and arguments["mandatory_nodes"][0] != "undefined":
            mandatory_nodes = arguments["mandatory_nodes"][0].split(",")
        return mandatory_nodes
