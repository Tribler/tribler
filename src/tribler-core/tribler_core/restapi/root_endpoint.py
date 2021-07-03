from tribler_core.restapi.rest_endpoint import RESTEndpoint


class RootEndpoint(RESTEndpoint):
    """
    The root endpoint of the Tribler HTTP API is the root resource in the request tree.
    It will dispatch requests regarding torrents, channels, settings etc to the right child endpoint.
    """
    pass
