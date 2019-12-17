from Tribler.Core.Modules.restapi.rest_endpoint import RESTEndpoint
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


class RootEndpoint(RESTEndpoint):

    def setup_routes(self):
        endpoints = {'/metadata': MetadataEndpoint,
                     '/channels': ChannelsEndpoint,
                     '/collections': ChannelsEndpoint,
                     '/events': EventsEndpoint,
                     '/state': StateEndpoint,
                     '/shutdown': ShutdownEndpoint,
                     '/settings': SettingsEndpoint,
                     '/downloads': DownloadsEndpoint,
                     '/debug': DebugEndpoint,
                     '/trustchain': TrustchainEndpoint,
                     '/statistics': StatisticsEndpoint,
                     '/libtorrent': LibTorrentEndpoint,
                     '/torrentinfo': TorrentInfoEndpoint,
                     '/search': SearchEndpoint,
                     '/ipv8': IPv8Endpoint,
                     '/market': MarketEndpoint,
                     '/wallets': WalletsEndpoint}
        for path, ep_cls in endpoints.items():
            self.add_endpoint(path, ep_cls(None))
