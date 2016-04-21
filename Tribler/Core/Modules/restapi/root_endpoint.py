from twisted.web import resource
from Tribler.Core.Modules.restapi.my_channel_endpoint import MyChannelEndpoint


class RootEndpoint(resource.Resource):
    """
    The root endpoint of the Tribler HTTP API is the root resource in the request tree.
    It will dispatch requests regarding torrents, channels, settings etc to the right child endpoint.
    """

    def __init__(self, session):
        resource.Resource.__init__(self)
        self.session = session

        self.my_channel_endpoint = MyChannelEndpoint(self.session)
        self.putChild("mychannel", self.my_channel_endpoint)
