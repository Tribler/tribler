from twisted.web import resource
from Tribler.Core.Modules.restapi.my_channel_endpoint import MyChannelEndpoint
from Tribler.Core.Modules.restapi.settings_endpoint import SettingsEndpoint
from Tribler.Core.Modules.restapi.variables_endpoint import VariablesEndpoint


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

        self.settings_endpoint = SettingsEndpoint(self.session)
        self.putChild("settings", self.settings_endpoint)

        self.variables_endpoint = VariablesEndpoint(self.session)
        self.putChild("variables", self.variables_endpoint)
