"""
Handle HTTP requests for the trust display, whilst validating the arguments and using them in the query.
"""
import json

from twisted.web import http, resource


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
    def return_400(request, message="your request seems to be wrong"):
        """
        Return a HTTP Code 400 with the given message.

        :param request: the request which has to be changed
        :param message: the error message which is used in the JSON string
        :return: the error message formatted in JSON
        """
        request.setResponseCode(http.BAD_REQUEST)
        return json.dumps({"error": message})

    def render_GET(self, request):
        """
        Process the GET request which retrieves the information used by the GUI Trust Display window.

        .. http:get:: /display?focus_node=(string: public key)&neighbor_level=(int: neighbor_level)

        A GET request to this endpoint returns the data from the multichain. This data is retrieved from the multichain
        database and will be focused around the given focus node. The neighbor_level parameter specifies which nodes
        are taken into consideration (e.g. a neighbor_level of 2 indicates that only the focus node, it's neighbors
        and the neighbors of those neighbors are taken into consideration). Please note that the neighbor_level
        parameter is optional; if the parameter is not set, a neighbor_level of 1 is assumed.

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
                    "neighbor_level: 1
                    "nodes": [{
                        "public_key": "xyz",
                        "total_up": 12736457,
                        "total_down": 1827364
                    }, ...],
                    "edges": [{
                        "from": "xyz",
                        "to": "xyz_n1",
                        "size": 12384
                    }, ...]
                }

        :param request: the HTTP GET request which specifies the focus node and optionally the neighbor level
        :return: the node data formatted in JSON
        """
        if "focus_node" not in request.args:
            return DisplayEndpoint.return_400(request, "focus_node parameter missing")

        if len(request.args["focus_node"]) < 1 or len(request.args["focus_node"][0]) == 0:
            return DisplayEndpoint.return_400(request, "focus_node parameter empty")

        neighbor_level = 1
        # Note that isdigit() checks if all chars are numbers, hence negative numbers are not possible to be set
        if "neighbor_level" in request.args and len(request.args["neighbor_level"]) > 0 and \
                request.args["neighbor_level"][0].isdigit():
            neighbor_level = int(request.args["neighbor_level"][0])

        # TODO: Remove dummy return and change to aggregated data calculation
        return json.dumps({"focus_node": request.args["focus_node"][0],
                           "neighbor_level": neighbor_level,
                           "nodes": [{"public_key": "xyz", "total_up": 0, "total_down": 0}],
                           "edges": []})
