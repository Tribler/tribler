import json
from twisted.web import resource


class DebugEndpoint(resource.Resource):
    """
    This class is responsible for dispatching various requests to debug endpoints.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

        child_handler_dict = {"communities": DebugCommunitiesEndpoint}

        for path, child_cls in child_handler_dict.iteritems():
            self.putChild(path, child_cls(self.session))


class DebugCommunitiesEndpoint(resource.Resource):
    """
    A GET request to this endpoint will return statistics about the loaded communities in Tribler.

    Example response (partially since the full response it too large to display):
    {
        "communities": {
            "<ChannelCommunity>: b9754da88799ff2dc4042325bd8640d3a5685100": {
                "Sync bloom created": "8",
                "Statistics": {
                    "outgoing": {
                        "-caused by missing-proof-": "1",
                        "dispersy-puncture-request": "8",
                        ...
                    },
                "Sync bloom reused":"0",
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
        return json.dumps(self.session.get_statistics())
