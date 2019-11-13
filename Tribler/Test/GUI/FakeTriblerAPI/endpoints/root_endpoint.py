from __future__ import absolute_import

from twisted.web import resource

from Tribler.Test.GUI.FakeTriblerAPI.endpoints.channels_endpoint import ChannelsEndpoint
from Tribler.Test.GUI.FakeTriblerAPI.endpoints.debug_endpoint import DebugEndpoint
from Tribler.Test.GUI.FakeTriblerAPI.endpoints.downloads_endpoint import DownloadsEndpoint
from Tribler.Test.GUI.FakeTriblerAPI.endpoints.events_endpoint import EventsEndpoint
from Tribler.Test.GUI.FakeTriblerAPI.endpoints.ipv8_endpoint import IPv8Endpoint
from Tribler.Test.GUI.FakeTriblerAPI.endpoints.libtorrent_endpoint import LibTorrentEndpoint
from Tribler.Test.GUI.FakeTriblerAPI.endpoints.market_endpoint import MarketEndpoint
from Tribler.Test.GUI.FakeTriblerAPI.endpoints.metadata_endpoint import MetadataEndpoint
from Tribler.Test.GUI.FakeTriblerAPI.endpoints.search_endpoint import SearchEndpoint
from Tribler.Test.GUI.FakeTriblerAPI.endpoints.settings_endpoint import SettingsEndpoint
from Tribler.Test.GUI.FakeTriblerAPI.endpoints.shutdown_endpoint import ShutdownEndpoint
from Tribler.Test.GUI.FakeTriblerAPI.endpoints.state_endpoint import StateEndpoint
from Tribler.Test.GUI.FakeTriblerAPI.endpoints.statistics_endpoint import StatisticsEndpoint
from Tribler.Test.GUI.FakeTriblerAPI.endpoints.torrentinfo_endpoint import TorrentInfoEndpoint
from Tribler.Test.GUI.FakeTriblerAPI.endpoints.trustchain_endpoint import TrustchainEndpoint
from Tribler.Test.GUI.FakeTriblerAPI.endpoints.wallets_endpoint import WalletsEndpoint


class RootEndpoint(resource.Resource):
    def __init__(self):
        resource.Resource.__init__(self)

        self.events_endpoint = EventsEndpoint()
        self.putChild(b"events", self.events_endpoint)

        child_handler_dict = {
            b"metadata": MetadataEndpoint,
            b"channels": ChannelsEndpoint,
            b"collections": ChannelsEndpoint,
            b"settings": SettingsEndpoint,
            b"search": SearchEndpoint,
            b"downloads": DownloadsEndpoint,
            b"trustchain": TrustchainEndpoint,
            b"statistics": StatisticsEndpoint,
            b"state": StateEndpoint,
            b"torrentinfo": TorrentInfoEndpoint,
            b"wallets": WalletsEndpoint,
            b"market": MarketEndpoint,
            b"shutdown": ShutdownEndpoint,
            b"debug": DebugEndpoint,
            b"ipv8": IPv8Endpoint,
            b"libtorrent": LibTorrentEndpoint,
        }

        for path, child_cls in child_handler_dict.items():
            self.putChild(path, child_cls())
