from pydantic import BaseSettings, Extra

from tribler_core.components.bandwidth_accounting.settings import BandwidthAccountingSettings
from tribler_core.components.gigachannel.community.settings import ChantSettings
from tribler_core.components.masterkey.settings import BootstrapSettings, DHTSettings, DiscoveryCommunitySettings, \
    Ipv8Settings, \
    TrustchainSettings, WatchFolderSettings
from tribler_core.modules.libtorrent.settings import DownloadDefaultsSettings, LibtorrentSettings
from tribler_core.modules.popularity.settings import PopularityCommunitySettings
from tribler_core.modules.remote_query_community.settings import RemoteQueryCommunitySettings
from tribler_core.modules.resource_monitor.settings import ResourceMonitorSettings
from tribler_core.modules.torrent_checker.settings import TorrentCheckerSettings
from tribler_core.modules.tunnel.community.settings import TunnelCommunitySettings
from tribler_core.restapi.settings import APISettings
from tribler_core.settings import ErrorHandlingSettings, GeneralSettings


class TriblerConfigSections(BaseSettings):
    """ Base Tribler config class that contains section listing.
    """

    class Config:
        extra = Extra.ignore  # ignore extra attributes during model initialization

    general: GeneralSettings = GeneralSettings()
    error_handling: ErrorHandlingSettings = ErrorHandlingSettings()
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
