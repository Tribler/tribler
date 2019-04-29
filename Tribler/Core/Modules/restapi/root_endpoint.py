from __future__ import absolute_import

from twisted.web import resource

from Tribler.Core.Modules.restapi.create_torrent_endpoint import CreateTorrentEndpoint
from Tribler.Core.Modules.restapi.debug_endpoint import DebugEndpoint
from Tribler.Core.Modules.restapi.downloads_endpoint import DownloadsEndpoint
from Tribler.Core.Modules.restapi.events_endpoint import EventsEndpoint
from Tribler.Core.Modules.restapi.libtorrent_endpoint import LibTorrentEndpoint
from Tribler.Core.Modules.restapi.market_endpoint import MarketEndpoint
from Tribler.Core.Modules.restapi.metadata_endpoint import MetadataEndpoint
from Tribler.Core.Modules.restapi.mychannel_endpoint import MyChannelEndpoint
from Tribler.Core.Modules.restapi.search_endpoint import SearchEndpoint
from Tribler.Core.Modules.restapi.settings_endpoint import SettingsEndpoint
from Tribler.Core.Modules.restapi.shutdown_endpoint import ShutdownEndpoint
from Tribler.Core.Modules.restapi.state_endpoint import StateEndpoint
from Tribler.Core.Modules.restapi.statistics_endpoint import StatisticsEndpoint
from Tribler.Core.Modules.restapi.torrentinfo_endpoint import TorrentInfoEndpoint
from Tribler.Core.Modules.restapi.trustchain_endpoint import TrustchainEndpoint
from Tribler.Core.Modules.restapi.trustview_endpoint import TrustViewEndpoint
from Tribler.Core.Modules.restapi.wallets_endpoint import WalletsEndpoint
from Tribler.pyipv8.ipv8.REST.root_endpoint import RootEndpoint as IPV8RootEndpoint


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
        self.shutdown_endpoint = ShutdownEndpoint(self.session)
        self.putChild(b"events", self.events_endpoint)
        self.putChild(b"state", self.state_endpoint)
        self.putChild(b"shutdown", self.shutdown_endpoint)

    def start_endpoints(self):
        """
        This method is only called when Tribler has started. It enables the other endpoints that are dependent
        on a fully started Tribler.
        """
        child_handler_dict = {
            b"settings": SettingsEndpoint,
            b"downloads": DownloadsEndpoint,
            b"createtorrent": CreateTorrentEndpoint,
            b"debug": DebugEndpoint,
            b"shutdown": ShutdownEndpoint,
            b"trustchain": TrustchainEndpoint,
            b"trustview": TrustViewEndpoint,
            b"statistics": StatisticsEndpoint,
            b"market": MarketEndpoint,
            b"wallets": WalletsEndpoint,
            b"libtorrent": LibTorrentEndpoint,
            b"torrentinfo": TorrentInfoEndpoint,
            b"metadata": MetadataEndpoint,
            b"mychannel": MyChannelEndpoint,
            b"search": SearchEndpoint
        }

        for path, child_cls in child_handler_dict.items():
            self.putChild(path, child_cls(self.session))

        if self.session.config.get_ipv8_enabled():
            self.putChild(b"ipv8", IPV8RootEndpoint(self.session.lm.ipv8))

        self.getChildWithDefault(b"search", None).events_endpoint = self.events_endpoint
