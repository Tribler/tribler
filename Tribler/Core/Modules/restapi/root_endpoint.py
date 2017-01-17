from twisted.web import resource

from Tribler.Core.Modules.restapi.channels.channels_endpoint import ChannelsEndpoint
from Tribler.Core.Modules.restapi.channels.my_channel_endpoint import MyChannelEndpoint
from Tribler.Core.Modules.restapi.create_torrent_endpoint import CreateTorrentEndpoint
from Tribler.Core.Modules.restapi.debug_endpoint import DebugEndpoint
from Tribler.Core.Modules.restapi.downloads_endpoint import DownloadsEndpoint
from Tribler.Core.Modules.restapi.events_endpoint import EventsEndpoint
from Tribler.Core.Modules.restapi.multichain_endpoint import MultichainEndpoint
from Tribler.Core.Modules.restapi.search_endpoint import SearchEndpoint
from Tribler.Core.Modules.restapi.settings_endpoint import SettingsEndpoint
from Tribler.Core.Modules.restapi.shutdown_endpoint import ShutdownEndpoint
from Tribler.Core.Modules.restapi.state_endpoint import StateEndpoint
from Tribler.Core.Modules.restapi.statistics_endpoint import StatisticsEndpoint
from Tribler.Core.Modules.restapi.torrentinfo_endpoint import TorrentInfoEndpoint
from Tribler.Core.Modules.restapi.torrents_endpoint import TorrentsEndpoint
from Tribler.Core.Modules.restapi.variables_endpoint import VariablesEndpoint


class RootEndpoint(resource.Resource):
    """
    The root endpoint of the Tribler HTTP API is the root resource in the request tree.
    It will dispatch requests regarding torrents, channels, settings etc to the right child endpoint.
    """

    def __init__(self, session):
        """
        During the initialization of the REST API, we only start the event sockets and the state endpoint.
        We enable the other endpoints when Tribler has completed the starting procedure.
        """
        resource.Resource.__init__(self)
        self.session = session
        self.events_endpoint = EventsEndpoint(self.session)
        self.state_endpoint = StateEndpoint(self.session)
        self.putChild("events", self.events_endpoint)
        self.putChild("state", self.state_endpoint)

    def start_endpoints(self):
        """
        This method is only called when Tribler has started. It enables the other endpoints that are dependent
        on a fully started Tribler.
        """
        child_handler_dict = {"search": SearchEndpoint, "channels": ChannelsEndpoint, "mychannel": MyChannelEndpoint,
                              "settings": SettingsEndpoint, "variables": VariablesEndpoint,
                              "downloads": DownloadsEndpoint, "createtorrent": CreateTorrentEndpoint,
                              "torrents": TorrentsEndpoint, "debug": DebugEndpoint, "shutdown": ShutdownEndpoint,
                              "multichain": MultichainEndpoint, "statistics": StatisticsEndpoint,
                              "torrentinfo": TorrentInfoEndpoint}

        for path, child_cls in child_handler_dict.iteritems():
            self.putChild(path, child_cls(self.session))

        self.getChildWithDefault("search", None).events_endpoint = self.events_endpoint
