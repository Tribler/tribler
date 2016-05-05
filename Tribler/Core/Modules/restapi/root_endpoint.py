from twisted.web import resource

from Tribler.Core.Modules.restapi.channels_endpoint import ChannelsEndpoint
from Tribler.Core.Modules.restapi.events_endpoint import EventsEndpoint
from Tribler.Core.Modules.restapi.my_channel_endpoint import MyChannelEndpoint
from Tribler.Core.Modules.restapi.search_endpoint import SearchEndpoint
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

        child_handler_dict = {"search": SearchEndpoint, "channels": ChannelsEndpoint, "mychannel": MyChannelEndpoint,
                              "settings": SettingsEndpoint, "variables": VariablesEndpoint, "events": EventsEndpoint}

        for path, child_cls in child_handler_dict.iteritems():
            self.putChild(path, child_cls(self.session))
