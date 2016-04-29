import json

from twisted.web import resource


class VariablesEndpoint(resource.Resource):
    """
    This endpoint is responsible for handing all requests regarding runtime-defined variables in Tribler such as ports.

    A GET request to this endpoint returns all the runtime-defined variables in Tribler.

    Example GET response:
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

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

    def render_GET(self, request):
        """
        Returns the runtime-defined variables in Tribler in a JSON dictionary.
        """
        return json.dumps({"variables": {"ports": self.session.selected_ports}})
