from pydantic import BaseSettings, Extra

from tribler.core.components.bandwidth_accounting.settings import BandwidthAccountingSettings
from tribler.core.components.gigachannel.community.settings import ChantSettings
from tribler.core.components.ipv8.settings import (
    BootstrapSettings,
    DHTSettings,
    DiscoveryCommunitySettings,
    Ipv8Settings,
)
from tribler.core.components.key.settings import TrustchainSettings
from tribler.core.components.libtorrent.settings import DownloadDefaultsSettings, LibtorrentSettings
from tribler.core.components.metadata_store.remote_query_community.settings import RemoteQueryCommunitySettings
from tribler.core.components.popularity.settings import PopularityCommunitySettings
from tribler.core.components.resource_monitor.settings import ResourceMonitorSettings
from tribler.core.components.restapi.rest.settings import APISettings
from tribler.core.components.torrent_checker.settings import TorrentCheckerSettings
from tribler.core.components.tunnel.settings import TunnelCommunitySettings
from tribler.core.components.watch_folder.settings import WatchFolderSettings
from tribler.core.settings import GeneralSettings


class TriblerConfigSections(BaseSettings):
    """ Base Tribler config class that contains section listing.
    """

    class Config:
        extra = Extra.ignore  # ignore extra attributes during model initialization

    general: GeneralSettings = GeneralSettings()
    tunnel_community: TunnelCommunitySettings = TunnelCommunitySettings()
    bandwidth_accounting: BandwidthAccountingSettings = BandwidthAccountingSettings()
    bootstrap: BootstrapSettings = BootstrapSettings()
    ipv8: Ipv8Settings = Ipv8Settings()
    discovery_community: DiscoveryCommunitySettings = DiscoveryCommunitySettings()
    dht: DHTSettings = DHTSettings()
    trustchain: TrustchainSettings = TrustchainSettings()
    watch_folder: WatchFolderSettings = WatchFolderSettings()
    chant: ChantSettings = ChantSettings()
    torrent_checking: TorrentCheckerSettings = TorrentCheckerSettings()
    libtorrent: LibtorrentSettings = LibtorrentSettings()
    download_defaults: DownloadDefaultsSettings = DownloadDefaultsSettings()
    api: APISettings = APISettings()
    resource_monitor: ResourceMonitorSettings = ResourceMonitorSettings()
    popularity_community: PopularityCommunitySettings = PopularityCommunitySettings()
    remote_query_community: RemoteQueryCommunitySettings = RemoteQueryCommunitySettings()
