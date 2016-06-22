from twisted.web import resource

from endpoints.channels.channels_endpoint import ChannelsEndpoint
from endpoints.downloads_endpoint import DownloadsEndpoint
from endpoints.events_endpoint import EventsEndpoint
from endpoints.mychannel_endpoint import MyChannelEndpoint
from endpoints.search_endpoint import SearchEndpoint
from endpoints.torrents_endpoint import TorrentsEndpoint
from endpoints.variables_endpoint import VariablesEndpoint
from settings_endpoint import SettingsEndpoint


class RootEndpoint(resource.Resource):

    def __init__(self):
        resource.Resource.__init__(self)

        self.events_endpoint = EventsEndpoint()
        self.putChild("events", self.events_endpoint)

        self.search_endpoint = SearchEndpoint(self.events_endpoint)
        self.putChild("search", self.search_endpoint)

        child_handler_dict = {"channels": ChannelsEndpoint, "mychannel": MyChannelEndpoint,
                              "settings": SettingsEndpoint, "variables": VariablesEndpoint,
                              "downloads": DownloadsEndpoint, "torrents": TorrentsEndpoint}

        for path, child_cls in child_handler_dict.iteritems():
            self.putChild(path, child_cls())
