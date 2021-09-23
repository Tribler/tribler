from tribler_core.components.implementation.bandwidth_accounting import BandwidthAccountingComponent
from tribler_core.components.implementation.gigachannel import GigaChannelComponent
from tribler_core.components.implementation.gigachannel_manager import GigachannelManagerComponent
from tribler_core.components.implementation.ipv8 import Ipv8Component
from tribler_core.components.implementation.libtorrent import LibtorrentComponent
from tribler_core.components.implementation.masterkey import MasterKeyComponent
from tribler_core.components.implementation.metadata_store import MetadataStoreComponent
from tribler_core.components.implementation.payout import PayoutComponent
from tribler_core.components.implementation.popularity import PopularityComponent
from tribler_core.components.implementation.reporter import ReporterComponent
from tribler_core.components.implementation.resource_monitor import ResourceMonitorComponent
from tribler_core.components.implementation.restapi import RESTComponent
from tribler_core.components.implementation.socks_configurator import SocksServersComponent
from tribler_core.components.implementation.torrent_checker import TorrentCheckerComponent
from tribler_core.components.implementation.tunnels import TunnelsComponent
from tribler_core.components.implementation.upgrade import UpgradeComponent
from tribler_core.components.implementation.version_check import VersionCheckComponent
from tribler_core.components.implementation.watch_folder import WatchFolderComponent
from tribler_core.config.tribler_config import TriblerConfig


components_list = [
    ReporterComponent,
    RESTComponent,
    MetadataStoreComponent,
    Ipv8Component,
    MasterKeyComponent,
    LibtorrentComponent,
    GigaChannelComponent,
    PopularityComponent,
    BandwidthAccountingComponent,
    ResourceMonitorComponent,

    # these components are skipped if config.gui_test_mode == True
    SocksServersComponent,
    UpgradeComponent,
    TunnelsComponent,
    PayoutComponent,
    TorrentCheckerComponent,
    WatchFolderComponent,
    VersionCheckComponent,
    GigachannelManagerComponent,
]



