"""
Handle HTTP requests for the trust display, whilst validating the arguments and using them in the query.
"""
from binascii import hexlify
import json

from twisted.web import http, resource

from Tribler.Core.exceptions import OperationNotEnabledByConfigurationException
from Tribler.community.multichain.community import MultiChainCommunity


class DisplayEndpoint(resource.Resource):
    """
    Handle HTTP requests for the trust display.
    """

    def __init__(self, session):
        """
        Initialize the DisplayEndpoint and make a session an attribute from the instance.

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
        Get the MultiChain community from the session.

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
        Process the GET request which retrieves the information used by the GUI Trust Display window.

        .. http:get:: /display?focus_node=(string: public key)&neighbor_level=(int: neighbor_level)

        A GET request to this endpoint returns the data from the multichain. This data is retrieved from the multichain
        database and will be focused around the given focus node. The neighbor_level parameter specifies which nodes
        are taken into consideration (e.g. a neighbor_level of 2 indicates that only the focus node, it's neighbors
        and the neighbors of those neighbors are taken into consideration).

        Note: the parameters are handled as follows:
        - focus_node
            - Not given: HTTP 400
            - Non-String value: HTTP 400
            - "self": Multichain Community public key
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

                curl -X GET http://localhost:8085/display?focus_node=xyz

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
        if "focus_node" not in request.args:
            return DisplayEndpoint.return_error(request, message="focus_node parameter missing")

        if len(request.args["focus_node"]) < 1 or len(request.args["focus_node"][0]) == 0:
            return DisplayEndpoint.return_error(request, message="focus_node parameter empty")

        focus_node = request.args["focus_node"][0]
        if isinstance(focus_node, basestring):
            if request.args["focus_node"][0] == "self":
                try:
                    mc_community = self.get_multi_chain_community()
                except OperationNotEnabledByConfigurationException as exc:
                    return DisplayEndpoint.return_error(request, status_code=http.NOT_FOUND, message=exc.args)
                focus_node = hexlify(mc_community.my_member.public_key)
            else:
                focus_node = request.args["focus_node"][0]
        else:
            return DisplayEndpoint.return_error(request, message="focus_node was not a string")

        neighbor_level = 1
        # Note that isdigit() checks if all chars are numbers, hence negative numbers are not possible to be set
        if "neighbor_level" in request.args and len(request.args["neighbor_level"]) > 0 and \
                request.args["neighbor_level"][0].isdigit():
            neighbor_level = int(request.args["neighbor_level"][0])

        # TODO: Remove dummy return and change to aggregated data calculation
        return json.dumps({"focus_node": focus_node,
                           "neighbor_level": neighbor_level,
                           "nodes": [{"public_key": "xyz", "total_up": 0, "total_down": 0, "page_rank": 0.5}],
                           "edges": []})
