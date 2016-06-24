from twisted.web import resource

from Tribler.Core.Modules.restapi.channels_endpoint import ChannelsEndpoint
from Tribler.Core.Modules.restapi.downloads_endpoint import DownloadsEndpoint
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
        """
        During the initialization of the REST API, we only start the event sockets. We enable the other endpoints
        when Tribler has completed the starting procedure.
        """
        resource.Resource.__init__(self)
        self.session = session
        self.events_endpoint = EventsEndpoint(self.session)
        self.putChild("events", self.events_endpoint)

    def start_endpoints(self):
        """
        This method is only called when Tribler has started. It enables the other endpoints that are dependent
        on a fully started Tribler.
        """
        child_handler_dict = {"search": SearchEndpoint, "channels": ChannelsEndpoint, "mychannel": MyChannelEndpoint,
                              "settings": SettingsEndpoint, "variables": VariablesEndpoint,
                              "downloads": DownloadsEndpoint}

        for path, child_cls in child_handler_dict.iteritems():
            self.putChild(path, child_cls(self.session))

        self.getChildWithDefault("search", None).events_endpoint = self.events_endpoint
