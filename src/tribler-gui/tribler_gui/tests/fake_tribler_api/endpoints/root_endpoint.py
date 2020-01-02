from tribler_core.restapi.rest_endpoint import RESTEndpoint

from tribler_gui.tests.fake_tribler_api.endpoints.channels_endpoint import ChannelsEndpoint
from tribler_gui.tests.fake_tribler_api.endpoints.debug_endpoint import DebugEndpoint
from tribler_gui.tests.fake_tribler_api.endpoints.downloads_endpoint import DownloadsEndpoint
from tribler_gui.tests.fake_tribler_api.endpoints.events_endpoint import EventsEndpoint
from tribler_gui.tests.fake_tribler_api.endpoints.ipv8_endpoint import IPv8Endpoint
from tribler_gui.tests.fake_tribler_api.endpoints.libtorrent_endpoint import LibTorrentEndpoint
from tribler_gui.tests.fake_tribler_api.endpoints.market_endpoint import MarketEndpoint
from tribler_gui.tests.fake_tribler_api.endpoints.metadata_endpoint import MetadataEndpoint
from tribler_gui.tests.fake_tribler_api.endpoints.search_endpoint import SearchEndpoint
from tribler_gui.tests.fake_tribler_api.endpoints.settings_endpoint import SettingsEndpoint
from tribler_gui.tests.fake_tribler_api.endpoints.shutdown_endpoint import ShutdownEndpoint
from tribler_gui.tests.fake_tribler_api.endpoints.state_endpoint import StateEndpoint
from tribler_gui.tests.fake_tribler_api.endpoints.statistics_endpoint import StatisticsEndpoint
from tribler_gui.tests.fake_tribler_api.endpoints.torrentinfo_endpoint import TorrentInfoEndpoint
from tribler_gui.tests.fake_tribler_api.endpoints.trustchain_endpoint import TrustchainEndpoint
from tribler_gui.tests.fake_tribler_api.endpoints.wallets_endpoint import WalletsEndpoint


class RootEndpoint(RESTEndpoint):
    def setup_routes(self):
        endpoints = {
            '/metadata': MetadataEndpoint,
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
            '/wallets': WalletsEndpoint,
        }
        for path, ep_cls in endpoints.items():
            self.add_endpoint(path, ep_cls(None))
