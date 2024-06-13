from ipv8.REST.root_endpoint import RootEndpoint

from tribler.core.restapi.rest_endpoint import RESTEndpoint


class IPv8RootEndpoint(RootEndpoint, RESTEndpoint):
    """
    Make the IPv8 REST endpoint Tribler-compatible.
    """

    path = "/api/ipv8"

    def __init__(self) -> None:
        """
        Create a new IPv8 endpoint.
        """
        RESTEndpoint.__init__(self)
        RootEndpoint.__init__(self)

