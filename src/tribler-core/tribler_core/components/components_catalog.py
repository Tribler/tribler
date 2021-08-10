from tribler_core.components.interfaces.bandwidth_accounting import BandwidthAccountingComponent
from tribler_core.components.interfaces.gigachannel import GigaChannelComponent
from tribler_core.components.interfaces.gigachannel_manager import GigachannelManagerComponent
from tribler_core.components.interfaces.ipv8 import Ipv8Component
from tribler_core.components.interfaces.libtorrent import LibtorrentComponent
from tribler_core.components.interfaces.metadata_store import MetadataStoreComponent
from tribler_core.components.interfaces.payout import PayoutComponent
from tribler_core.components.interfaces.popularity import PopularityComponent
from tribler_core.components.interfaces.resource_monitor import ResourceMonitorComponent
from tribler_core.components.interfaces.reporter import ReporterComponent
from tribler_core.components.interfaces.restapi import RESTComponent
from tribler_core.components.interfaces.socks_configurator import SocksServersComponent
from tribler_core.components.interfaces.torrent_checker import TorrentCheckerComponent
from tribler_core.components.interfaces.masterkey import MasterKeyComponent
from tribler_core.components.interfaces.tunnels import TunnelsComponent
from tribler_core.components.interfaces.upgrade import UpgradeComponent
from tribler_core.components.interfaces.version_check import VersionCheckComponent
from tribler_core.components.interfaces.watch_folder import WatchFolderComponent
from tribler_core.config.tribler_config import TriblerConfig


def components_gen(config: TriblerConfig):
    components_list = [
        ReporterComponent,
        RESTComponent,
        MetadataStoreComponent,
        Ipv8Component,
        MasterKeyComponent,
        LibtorrentComponent,
        GigaChannelComponent,
        PopularityComponent,

        # these components are skipped if config.gui_test_mode == True
        SocksServersComponent,
        UpgradeComponent,
        TunnelsComponent,
        BandwidthAccountingComponent,
        PayoutComponent,
        TorrentCheckerComponent,
        WatchFolderComponent,
        ResourceMonitorComponent,
        VersionCheckComponent,
        GigachannelManagerComponent,
    ]
    for component in components_list:
        enable = component.should_be_enabled(config)
        if config.gui_test_mode and not component.enable_in_gui_test_mode:
            enable = False
        yield component, enable
