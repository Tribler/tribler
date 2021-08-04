from tribler_core.components.implementation.bandwidth_accounting import BandwidthAccountingComponentImp
from tribler_core.components.implementation.gigachannel import GigaChannelComponentImp
from tribler_core.components.implementation.gigachannel_manager import GigachannelManagerComponentImp
from tribler_core.components.implementation.ipv8 import (
    DHTDiscoveryCommunityComponentImp,
    DiscoveryCommunityComponentImp,
    Ipv8BootstrapperComponentImp,
    Ipv8ComponentImp,
    Ipv8PeerComponentImp,
)
from tribler_core.components.implementation.libtorrent import LibtorrentComponentImp
from tribler_core.components.implementation.metadata_store import MetadataStoreComponentImp
from tribler_core.components.implementation.payout import PayoutComponentImp
from tribler_core.components.implementation.popularity import PopularityComponentImp
from tribler_core.components.implementation.resource_monitor import ResourceMonitorComponentImp
from tribler_core.components.implementation.restapi import RESTComponentImp
from tribler_core.components.implementation.socks_configurator import SocksServersComponentImp
from tribler_core.components.implementation.torrent_checker import TorrentCheckerComponentImp
from tribler_core.components.implementation.tunnels import TunnelsComponentImp
from tribler_core.components.implementation.upgrade import UpgradeComponentImp
from tribler_core.components.implementation.version_check import VersionCheckComponentImp
from tribler_core.components.implementation.watch_folder import WatchFolderComponentImp
from tribler_core.config.tribler_config import TriblerConfig


def components_gen(config: TriblerConfig):
    components_list = [
        (SocksServersComponentImp,
         not config.core_test_mode and config.tunnel_community.enabled and config.libtorrent.enabled),
        (RESTComponentImp, config.api.http_enabled or config.api.https_enabled),
        (UpgradeComponentImp, config.upgrader_enabled and not config.core_test_mode),
        (MetadataStoreComponentImp, config.chant.enabled),
        (DHTDiscoveryCommunityComponentImp, config.ipv8.enabled and not config.core_test_mode),
        (Ipv8PeerComponentImp, config.ipv8.enabled),
        (Ipv8BootstrapperComponentImp, config.ipv8.enabled and not config.core_test_mode),
        (DiscoveryCommunityComponentImp, config.ipv8.enabled and not config.core_test_mode),
        (Ipv8ComponentImp, config.ipv8.enabled),
        (LibtorrentComponentImp, config.libtorrent.enabled),
        (TunnelsComponentImp, config.ipv8.enabled and config.tunnel_community.enabled and not config.core_test_mode),
        (BandwidthAccountingComponentImp, config.ipv8.enabled and not config.core_test_mode),
        (PayoutComponentImp, config.ipv8.enabled and not config.core_test_mode),
        (TorrentCheckerComponentImp, config.torrent_checking.enabled and not config.core_test_mode),
        (PopularityComponentImp, config.ipv8.enabled and config.popularity_community.enabled),
        (GigaChannelComponentImp, config.chant.enabled),
        (WatchFolderComponentImp, config.watch_folder.enabled and not config.core_test_mode),
        (ResourceMonitorComponentImp, config.resource_monitor.enabled and not config.core_test_mode),
        (VersionCheckComponentImp, config.general.version_checker_enabled and not config.core_test_mode),
        (GigachannelManagerComponentImp,
         (config.chant.enabled and
          config.chant.manager_enabled and
          config.libtorrent.enabled and
          not config.core_test_mode))
    ]

    for component, condition in components_list:
        if condition:
            yield component()
        else:
            mock_comp_implementation_class = type(component.__class__.__name__ + 'MockImp', (component,), {})
            yield mock_comp_implementation_class()
