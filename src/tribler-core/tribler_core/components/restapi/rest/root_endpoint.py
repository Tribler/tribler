from ipv8.REST.root_endpoint import RootEndpoint as IPV8RootEndpoint

from tribler_core.components.bandwidth_accounting.restapi.bandwidth_endpoint import BandwidthEndpoint
from tribler_core.components.libtorrent.restapi.create_torrent_endpoint import CreateTorrentEndpoint
from tribler_core.components.libtorrent.restapi.downloads_endpoint import DownloadsEndpoint
from tribler_core.components.libtorrent.restapi.libtorrent_endpoint import LibTorrentEndpoint
from tribler_core.components.libtorrent.restapi.torrentinfo_endpoint import TorrentInfoEndpoint
from tribler_core.components.metadata_store.restapi.channels_endpoint import ChannelsEndpoint
from tribler_core.components.metadata_store.restapi.metadata_endpoint import MetadataEndpoint
from tribler_core.components.metadata_store.restapi.remote_query_endpoint import RemoteQueryEndpoint
from tribler_core.components.metadata_store.restapi.search_endpoint import SearchEndpoint
from tribler_core.components.restapi.rest.debug_endpoint import DebugEndpoint
from tribler_core.components.restapi.rest.events_endpoint import EventsEndpoint
from tribler_core.components.restapi.rest.rest_endpoint import RESTEndpoint
from tribler_core.components.restapi.rest.settings_endpoint import SettingsEndpoint
from tribler_core.components.restapi.rest.shutdown_endpoint import ShutdownEndpoint
from tribler_core.components.restapi.rest.state_endpoint import StateEndpoint
from tribler_core.components.restapi.rest.statistics_endpoint import StatisticsEndpoint
from tribler_core.components.restapi.rest.trustview_endpoint import TrustViewEndpoint
from tribler_core.components.tag.restapi.tags_endpoint import TagsEndpoint
from tribler_core.components.upgrade.implementation.upgrader_endpoint import UpgraderEndpoint
from tribler_core.config.tribler_config import TriblerConfig
from tribler_core.utilities.utilities import froze_it


@froze_it
class RootEndpoint(RESTEndpoint):
    """
    The root endpoint of the Tribler HTTP API is the root resource in the request tree.
    It will dispatch requests regarding torrents, channels, settings etc to the right child endpoint.
    """

    def __init__(self, tribler_config: TriblerConfig, **kwargs):
        self.tribler_config = tribler_config
        super().__init__(**kwargs)

    def setup_routes(self):
        # Unfortunately, AIOHTTP endpoints cannot be added after the app has been started.
        # On the other hand, we have to start the state endpoint from the beginning, to
        # communicate with the upgrader . Thus, we start the endpoints immediately and
        # then gradually assign their properties during the core start process

        endpoints = {
            '/events': (EventsEndpoint, True),
            '/state': (StateEndpoint, True),
            '/shutdown': (ShutdownEndpoint, True),
            '/upgrader': (UpgraderEndpoint, self.tribler_config.upgrader_enabled),
            '/settings': (SettingsEndpoint, True),
            '/downloads': (DownloadsEndpoint, self.tribler_config.libtorrent.enabled),
            '/createtorrent': (CreateTorrentEndpoint, self.tribler_config.libtorrent.enabled),
            '/debug': (DebugEndpoint, True),
            '/bandwidth': (BandwidthEndpoint, True),
            '/trustview': (TrustViewEndpoint, True),
            '/statistics': (StatisticsEndpoint, True),
            '/libtorrent': (LibTorrentEndpoint, self.tribler_config.libtorrent.enabled),
            '/torrentinfo': (TorrentInfoEndpoint, self.tribler_config.libtorrent.enabled),
            '/metadata': (MetadataEndpoint, self.tribler_config.chant.enabled),
            '/channels': (ChannelsEndpoint, self.tribler_config.chant.enabled),
            '/collections': (ChannelsEndpoint, self.tribler_config.chant.enabled),
            '/search': (SearchEndpoint, self.tribler_config.chant.enabled),
            '/remote_query': (RemoteQueryEndpoint, self.tribler_config.chant.enabled),
            '/ipv8': (IPV8RootEndpoint, self.tribler_config.ipv8.enabled),
            '/tags': (TagsEndpoint, self.tribler_config.chant.enabled),
        }
        for path, (ep_cls, enabled) in endpoints.items():
            if enabled:
                self.add_endpoint(path, ep_cls())
