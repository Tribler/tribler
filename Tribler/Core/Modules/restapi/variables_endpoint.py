import json

from twisted.web import resource


class VariablesEndpoint(resource.Resource):
    """
    This endpoint is responsible for handing all requests regarding runtime-defined variables in Tribler such as ports.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

    def render_GET(self, request):
        """
        .. http:get:: /variables

        A GET request to this endpoint returns all the runtime-defined variables in Tribler.

            **Example request**:

            .. sourcecode:: none

                curl -X GET http://localhost:8085/variables

            **Example response**:

            .. sourcecode:: javascript

                {
                    "variables": {
                        "ports": {
                            "video~port": 1234,
                            "tunnel_community~socks5_listen_ports~1": 1235,
                            ...
                        },
                        ...
                    }
                }
        """
        return json.dumps({"variables": {"ports": self.session.selected_ports}})
