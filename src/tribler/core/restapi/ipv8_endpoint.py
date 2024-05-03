from ipv8.REST.root_endpoint import RootEndpoint

from tribler.core.restapi.rest_endpoint import RESTEndpoint


class IPv8RootEndpoint(RootEndpoint, RESTEndpoint):
    """
    Make the IPv8 REST endpoint Tribler-compatible.
    """

    path = "/ipv8"
