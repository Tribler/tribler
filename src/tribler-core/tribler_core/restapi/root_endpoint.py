from ipv8.REST.root_endpoint import RootEndpoint as IPV8RootEndpoint

from tribler_core.modules.bandwidth_accounting.bandwidth_endpoint import BandwidthEndpoint
from tribler_core.modules.libtorrent.restapi.create_torrent_endpoint import CreateTorrentEndpoint
from tribler_core.modules.libtorrent.restapi.downloads_endpoint import DownloadsEndpoint
from tribler_core.modules.libtorrent.restapi.libtorrent_endpoint import LibTorrentEndpoint
from tribler_core.modules.libtorrent.restapi.torrentinfo_endpoint import TorrentInfoEndpoint
from tribler_core.modules.metadata_store.restapi.channels_endpoint import ChannelsEndpoint
from tribler_core.modules.metadata_store.restapi.metadata_endpoint import MetadataEndpoint
from tribler_core.modules.metadata_store.restapi.remote_query_endpoint import RemoteQueryEndpoint
from tribler_core.modules.metadata_store.restapi.search_endpoint import SearchEndpoint
from tribler_core.restapi.debug_endpoint import DebugEndpoint
from tribler_core.restapi.events_endpoint import EventsEndpoint
from tribler_core.restapi.rest_endpoint import RESTEndpoint
from tribler_core.restapi.settings_endpoint import SettingsEndpoint
from tribler_core.restapi.shutdown_endpoint import ShutdownEndpoint
from tribler_core.restapi.state_endpoint import StateEndpoint
from tribler_core.restapi.statistics_endpoint import StatisticsEndpoint
from tribler_core.restapi.trustview_endpoint import TrustViewEndpoint
from tribler_core.upgrade.upgrader_endpoint import UpgraderEndpoint


class RootEndpoint(RESTEndpoint):
    """
    The root endpoint of the Tribler HTTP API is the root resource in the request tree.
    It will dispatch requests regarding torrents, channels, settings etc to the right child endpoint.
    """

    def setup_routes(self):
        endpoints = {'/events': EventsEndpoint,
                     '/state': StateEndpoint,
                     '/shutdown': ShutdownEndpoint,
                     '/upgrader': UpgraderEndpoint,
                     '/settings': SettingsEndpoint,
                     '/downloads': DownloadsEndpoint,
                     '/createtorrent': CreateTorrentEndpoint,
                     '/debug': DebugEndpoint,
                     '/bandwidth': BandwidthEndpoint,
                     '/trustview': TrustViewEndpoint,
                     '/statistics': StatisticsEndpoint,
                     '/libtorrent': LibTorrentEndpoint,
                     '/torrentinfo': TorrentInfoEndpoint,
                     '/metadata': MetadataEndpoint,
                     '/channels': ChannelsEndpoint,
                     '/collections': ChannelsEndpoint,  # FIXME: evil hack! Implement the real CollectionsEndpoint!
                     '/search': SearchEndpoint,
                     '/remote_query': RemoteQueryEndpoint,
                     }
        for path, ep_cls in endpoints.items():
            self.add_endpoint(path, ep_cls(self.session))

        if self.session.config.get_ipv8_enabled():
            self.add_endpoint('/ipv8', IPV8RootEndpoint())

    def set_ipv8_session(self, ipv8_session):
        if '/ipv8' in self.endpoints:
            self.endpoints['/ipv8'].initialize(ipv8_session)
