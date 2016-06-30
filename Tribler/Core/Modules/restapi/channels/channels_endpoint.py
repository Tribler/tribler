from Tribler.Core.Modules.restapi.channels.base_channels_endpoint import BaseChannelsEndpoint
from Tribler.Core.Modules.restapi.channels.channels_discovered_endpoint import ChannelsDiscoveredEndpoint
from Tribler.Core.Modules.restapi.channels.channels_popular_endpoint import ChannelsPopularEndpoint
from Tribler.Core.Modules.restapi.channels.channels_subscription_endpoint import ChannelsSubscribedEndpoint


class ChannelsEndpoint(BaseChannelsEndpoint):
    """
    This endpoint is responsible for handing all requests regarding channels in Tribler.
    """

    def __init__(self, session):
        BaseChannelsEndpoint.__init__(self, session)

        child_handler_dict = {"subscribed": ChannelsSubscribedEndpoint, "discovered": ChannelsDiscoveredEndpoint,
                              "popular": ChannelsPopularEndpoint}
        for path, child_cls in child_handler_dict.iteritems():
            self.putChild(path, child_cls(self.session))
