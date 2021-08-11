import pytest

from tribler_core.components import base
from tribler_core.components.base import Session, SessionError, get_session
from tribler_core.components.components_catalog import components_gen
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
    SocksServersComponent,
    UpgradeComponent,
    TunnelsComponent,
    PayoutComponent,
    TorrentCheckerComponent,
    WatchFolderComponent,
    VersionCheckComponent,
    GigachannelManagerComponent,
]


def test_components_gen(loop):
    config = TriblerConfig()
    components = list(components_gen(config))
    assert len(components) == len(components_list)
    for component, component_class in zip(components, components_list):
        assert isinstance(component, component_class)


def test_session_context_manager(loop, tribler_config):
    session1 = Session(tribler_config, [])
    session2 = Session(tribler_config, [])
    session3 = Session(tribler_config, [])

    with pytest.raises(SessionError, match="Default session was not set"):
        get_session()

    base.set_default_session(session1)
    assert get_session() is session1

    with session2:
        assert get_session() is session2
        with session3:
            assert get_session() is session3
        assert get_session() is session2
    assert get_session() is session1

    base.set_default_session(None)
    with pytest.raises(SessionError, match="Default session was not set"):
        get_session()


def test_components_creation(loop, tribler_config):
    for interface in components_list:
        implementation = interface.make_implementation(tribler_config, True)
        assert isinstance(implementation, interface)
        assert implementation.__class__.__name__.endswith('Imp')

        mock = interface.make_implementation(tribler_config, False)
        assert isinstance(mock, interface)
        assert mock.__class__.__name__.endswith('Mock')


async def test_masterkey_component(loop, tribler_config):
    session = Session(tribler_config, [
        MasterKeyComponent.make_implementation(tribler_config, True)
    ])
    with session:
        comp = MasterKeyComponent.imp()
        assert comp.session is session
        assert isinstance(comp, MasterKeyComponent) and comp.__class__.__name__ == 'MasterKeyComponentImp'

        await session.start()
        assert comp.started.is_set()
        assert not comp.failed

        session.shutdown_event.set()
        await session.shutdown()
        assert comp.stopped


async def test_reporter_component(loop, tribler_config):
    session = Session(tribler_config, [
        MasterKeyComponent.make_implementation(tribler_config, True),
        ReporterComponent.make_implementation(tribler_config, True),
    ])
    with session:
        comp = ReporterComponent.imp()
        assert comp.session is session
        assert isinstance(comp, ReporterComponent) and comp.__class__.__name__ == 'ReporterComponentImp'

        await session.start()
        assert comp.started.is_set()
        assert not comp.failed

        session.shutdown_event.set()
        await session.shutdown()
        assert comp.stopped

async def test_rest_component(loop, tribler_config):
    # FIXME: the next line was added to avoid  'Task was destroyed but it is pending!' error
    tribler_config.api.http_enabled = True

    session = Session(tribler_config, [
        MasterKeyComponent.make_implementation(tribler_config, True),
        ReporterComponent.make_implementation(tribler_config, True),
        RESTComponent.make_implementation(tribler_config, True),
    ])
    with session:
        comp = RESTComponent.imp()
        assert comp.session is session
        assert isinstance(comp, RESTComponent) and comp.__class__.__name__ == 'RESTComponentImp'

        await session.start()
        assert comp.started.is_set()
        assert not comp.failed

        session.shutdown_event.set()
        await session.shutdown()
        assert comp.stopped


async def test_upgrade_component(loop, tribler_config):
    # FIXME: the next line was added to avoid  'Task was destroyed but it is pending!' error
    tribler_config.api.http_enabled = True

    session = Session(tribler_config, [
        MasterKeyComponent.make_implementation(tribler_config, True),
        ReporterComponent.make_implementation(tribler_config, True),
        RESTComponent.make_implementation(tribler_config, True),
        UpgradeComponent.make_implementation(tribler_config, True),
    ])
    with session:
        comp = UpgradeComponent.imp()
        assert comp.session is session
        assert isinstance(comp, UpgradeComponent) and comp.__class__.__name__ == 'UpgradeComponentImp'

        await session.start()
        assert comp.started.is_set()
        assert not comp.failed

        session.shutdown_event.set()
        await session.shutdown()
        assert comp.stopped


async def test_ipv8_component(loop, tribler_config):
    # FIXME: the next line was added to avoid  'Task was destroyed but it is pending!' error
    tribler_config.api.http_enabled = True

    tribler_config.ipv8.enabled = True
    session = Session(tribler_config, [
        MasterKeyComponent.make_implementation(tribler_config, True),
        ReporterComponent.make_implementation(tribler_config, True),
        RESTComponent.make_implementation(tribler_config, True),
        Ipv8Component.make_implementation(tribler_config, True),
    ])
    with session:
        comp = Ipv8Component.imp()
        assert comp.session is session
        assert isinstance(comp, Ipv8Component) and comp.__class__.__name__ == 'Ipv8ComponentImp'

        await session.start()
        assert comp.started.is_set()
        assert not comp.failed

        session.shutdown_event.set()
        await session.shutdown()
        assert comp.stopped


async def test_libtorrent_component(loop, tribler_config):
    # FIXME: the next line was added to avoid  'Task was destroyed but it is pending!' error
    tribler_config.api.http_enabled = True

    tribler_config.libtorrent.enabled = True
    tribler_config.chant.enabled = True
    session = Session(tribler_config, [
        MasterKeyComponent.make_implementation(tribler_config, True),
        ReporterComponent.make_implementation(tribler_config, True),
        RESTComponent.make_implementation(tribler_config, True),
        UpgradeComponent.make_implementation(tribler_config, True),
        SocksServersComponent.make_implementation(tribler_config, True),
        LibtorrentComponent.make_implementation(tribler_config, True),
    ])
    with session:
        comp = LibtorrentComponent.imp()
        assert comp.session is session
        assert isinstance(comp, LibtorrentComponent) and comp.__class__.__name__ == 'LibtorrentComponentImp'

        await session.start()
        assert comp.started.is_set()
        assert not comp.failed

        session.shutdown_event.set()
        await session.shutdown()
        assert comp.stopped


async def test_metadata_store_component(loop, tribler_config):
    # FIXME: the next line was added to avoid  'Task was destroyed but it is pending!' error
    tribler_config.api.http_enabled = True

    tribler_config.libtorrent.enabled = True
    tribler_config.chant.enabled = True
    session = Session(tribler_config, [
        MasterKeyComponent.make_implementation(tribler_config, True),
        ReporterComponent.make_implementation(tribler_config, True),
        RESTComponent.make_implementation(tribler_config, True),
        UpgradeComponent.make_implementation(tribler_config, True),
        MetadataStoreComponent.make_implementation(tribler_config, True),
    ])
    with session:
        comp = MetadataStoreComponent.imp()
        assert comp.session is session
        assert isinstance(comp, MetadataStoreComponent) and comp.__class__.__name__ == 'MetadataStoreComponentImp'

        await session.start()
        assert comp.started.is_set()
        assert not comp.failed

        session.shutdown_event.set()
        await session.shutdown()
        assert comp.stopped


async def test_gigachannel_component(loop, tribler_config):
    # FIXME: the next line was added to avoid  'Task was destroyed but it is pending!' error
    tribler_config.api.http_enabled = True

    tribler_config.ipv8.enabled = True
    tribler_config.libtorrent.enabled = True
    tribler_config.chant.enabled = True
    session = Session(tribler_config, [
        MasterKeyComponent.make_implementation(tribler_config, True),
        ReporterComponent.make_implementation(tribler_config, True),
        RESTComponent.make_implementation(tribler_config, True),
        Ipv8Component.make_implementation(tribler_config, True),
        UpgradeComponent.make_implementation(tribler_config, True),
        MetadataStoreComponent.make_implementation(tribler_config, True),
        GigaChannelComponent.make_implementation(tribler_config, True),
    ])
    with session:
        comp = GigaChannelComponent.imp()
        assert comp.session is session
        assert isinstance(comp, GigaChannelComponent) and comp.__class__.__name__ == 'GigaChannelComponentImp'

        await session.start()
        assert comp.started.is_set()
        assert not comp.failed

        session.shutdown_event.set()
        await session.shutdown()
        assert comp.stopped


async def test_popularity_component(loop, tribler_config): ###
    # FIXME: the next line was added to avoid  'Task was destroyed but it is pending!' error
    tribler_config.api.http_enabled = True

    tribler_config.ipv8.enabled = True
    tribler_config.libtorrent.enabled = True
    tribler_config.chant.enabled = True
    session = Session(tribler_config, [
        MasterKeyComponent.make_implementation(tribler_config, True),
        ReporterComponent.make_implementation(tribler_config, True),
        RESTComponent.make_implementation(tribler_config, True),
        Ipv8Component.make_implementation(tribler_config, True),
        UpgradeComponent.make_implementation(tribler_config, True),
        MetadataStoreComponent.make_implementation(tribler_config, True),
        SocksServersComponent.make_implementation(tribler_config, True),
        LibtorrentComponent.make_implementation(tribler_config, True),
        TorrentCheckerComponent.make_implementation(tribler_config, True),
        PopularityComponent.make_implementation(tribler_config, True)
    ])
    with session:
        comp = PopularityComponent.imp()
        assert comp.session is session
        assert isinstance(comp, PopularityComponent) and comp.__class__.__name__ == 'PopularityComponentImp'

        await session.start()
        assert comp.started.is_set()
        assert not comp.failed

        session.shutdown_event.set()
        await session.shutdown()
        assert comp.stopped

async def test_socks_servers_component(loop, tribler_config):
    session = Session(tribler_config, [
        MasterKeyComponent.make_implementation(tribler_config, True),
        ReporterComponent.make_implementation(tribler_config, True),
        SocksServersComponent.make_implementation(tribler_config, True),
    ])
    with session:
        comp = SocksServersComponent.imp()
        assert comp.session is session
        assert isinstance(comp, SocksServersComponent) and comp.__class__.__name__ == 'SocksServersComponentImp'

        await session.start()
        assert comp.started.is_set()
        assert not comp.failed

        session.shutdown_event.set()
        await session.shutdown()
        assert comp.stopped


async def test_tunnels_component(loop, tribler_config): ###
    # FIXME: the next line was added to avoid  'Task was destroyed but it is pending!' error
    tribler_config.api.http_enabled = True

    tribler_config.ipv8.enabled = True
    tribler_config.libtorrent.enabled = True
    tribler_config.chant.enabled = True
    session = Session(tribler_config, [
        MasterKeyComponent.make_implementation(tribler_config, True),
        ReporterComponent.make_implementation(tribler_config, True),
        RESTComponent.make_implementation(tribler_config, True),
        Ipv8Component.make_implementation(tribler_config, True),
        UpgradeComponent.make_implementation(tribler_config, True),
        BandwidthAccountingComponent.make_implementation(tribler_config, True),
        SocksServersComponent.make_implementation(tribler_config, True),
        LibtorrentComponent.make_implementation(tribler_config, True),
        TunnelsComponent.make_implementation(tribler_config, True),
    ])
    with session:
        comp = TunnelsComponent.imp()
        assert comp.session is session
        assert isinstance(comp, TunnelsComponent) and comp.__class__.__name__ == 'TunnelsComponentImp'

        await session.start()
        assert comp.started.is_set()
        assert not comp.failed

        session.shutdown_event.set()
        await session.shutdown()
        assert comp.stopped


async def test_bandwidth_accounting_component(loop, tribler_config):
    # FIXME: the next line was added to avoid  'Task was destroyed but it is pending!' error
    tribler_config.api.http_enabled = True

    tribler_config.ipv8.enabled = True
    session = Session(tribler_config, [
        MasterKeyComponent.make_implementation(tribler_config, True),
        ReporterComponent.make_implementation(tribler_config, True),
        Ipv8Component.make_implementation(tribler_config, True),
        RESTComponent.make_implementation(tribler_config, True),
        UpgradeComponent.make_implementation(tribler_config, True),
        BandwidthAccountingComponent.make_implementation(tribler_config, True),
    ])
    with session:
        comp = BandwidthAccountingComponent.imp()
        assert comp.session is session
        assert isinstance(comp, BandwidthAccountingComponent) and comp.__class__.__name__ == 'BandwidthAccountingComponentImp'

        await session.start()
        assert comp.started.is_set()
        assert not comp.failed

        session.shutdown_event.set()
        await session.shutdown()
        assert comp.stopped


async def test_payout_component(loop, tribler_config):
    # FIXME: the next line was added to avoid  'Task was destroyed but it is pending!' error
    tribler_config.api.http_enabled = True

    tribler_config.ipv8.enabled = True
    session = Session(tribler_config, [
        MasterKeyComponent.make_implementation(tribler_config, True),
        ReporterComponent.make_implementation(tribler_config, True),
        RESTComponent.make_implementation(tribler_config, True),
        Ipv8Component.make_implementation(tribler_config, True),
        UpgradeComponent.make_implementation(tribler_config, True),
        BandwidthAccountingComponent.make_implementation(tribler_config, True),
        PayoutComponent.make_implementation(tribler_config, True),
    ])
    with session:
        comp = PayoutComponent.imp()
        assert comp.session is session
        assert isinstance(comp, PayoutComponent) and comp.__class__.__name__ == 'PayoutComponentImp'

        await session.start()
        assert comp.started.is_set()
        assert not comp.failed

        session.shutdown_event.set()
        await session.shutdown()
        assert comp.stopped


async def test_torrent_checker_component(loop, tribler_config): ###
    # FIXME: the next line was added to avoid  'Task was destroyed but it is pending!' error
    tribler_config.api.http_enabled = True

    tribler_config.libtorrent.enabled = True
    tribler_config.chant.enabled = True
    session = Session(tribler_config, [
        MasterKeyComponent.make_implementation(tribler_config, True),
        ReporterComponent.make_implementation(tribler_config, True),
        UpgradeComponent.make_implementation(tribler_config, True),
        RESTComponent.make_implementation(tribler_config, True),
        MetadataStoreComponent.make_implementation(tribler_config, True),
        LibtorrentComponent.make_implementation(tribler_config, True),
        SocksServersComponent.make_implementation(tribler_config, True),
        TorrentCheckerComponent.make_implementation(tribler_config, True),
    ])
    with session:
        comp = TorrentCheckerComponent.imp()
        assert comp.session is session
        assert isinstance(comp, TorrentCheckerComponent) and comp.__class__.__name__ == 'TorrentCheckerComponentImp'

        await session.start()
        assert comp.started.is_set()
        assert not comp.failed

        session.shutdown_event.set()
        await session.shutdown()
        assert comp.stopped


async def test_watch_folder_component(loop, tribler_config):
    # FIXME: the next line was added to avoid  'Task was destroyed but it is pending!' error
    tribler_config.api.http_enabled = True

    tribler_config.libtorrent.enabled = True
    tribler_config.chant.enabled = True
    session = Session(tribler_config, [
        MasterKeyComponent.make_implementation(tribler_config, True),
        ReporterComponent.make_implementation(tribler_config, True),
        RESTComponent.make_implementation(tribler_config, True),
        UpgradeComponent.make_implementation(tribler_config, True),
        SocksServersComponent.make_implementation(tribler_config, True),
        LibtorrentComponent.make_implementation(tribler_config, True),
        WatchFolderComponent.make_implementation(tribler_config, True),
    ])
    with session:
        comp = WatchFolderComponent.imp()
        assert comp.session is session
        assert isinstance(comp, WatchFolderComponent) and comp.__class__.__name__ == 'WatchFolderComponentImp'

        await session.start()
        assert comp.started.is_set()
        assert not comp.failed

        session.shutdown_event.set()
        await session.shutdown()
        assert comp.stopped


async def test_resourcemonitorcomponent(loop, tribler_config): ###
    # FIXME: the next line was added to avoid  'Task was destroyed but it is pending!' error
    tribler_config.api.http_enabled = True

    tribler_config.ipv8.enabled = True
    tribler_config.libtorrent.enabled = True
    tribler_config.chant.enabled = True
    session = Session(tribler_config, [
        MasterKeyComponent.make_implementation(tribler_config, True),
        ReporterComponent.make_implementation(tribler_config, True),
        RESTComponent.make_implementation(tribler_config, True),
        UpgradeComponent.make_implementation(tribler_config, True),
        Ipv8Component.make_implementation(tribler_config, True),
        BandwidthAccountingComponent.make_implementation(tribler_config, True),
        SocksServersComponent.make_implementation(tribler_config, True),
        LibtorrentComponent.make_implementation(tribler_config, True),
        TunnelsComponent.make_implementation(tribler_config, True),
        ResourceMonitorComponent.make_implementation(tribler_config, True),
    ])
    with session:
        comp = ResourceMonitorComponent.imp()
        assert comp.session is session
        assert isinstance(comp, ResourceMonitorComponent) and comp.__class__.__name__ == 'ResourceMonitorComponentImp'

        await session.start()
        assert comp.started.is_set()
        assert not comp.failed

        session.shutdown_event.set()
        await session.shutdown()
        assert comp.stopped


async def test_versioncheckcomponent(loop, tribler_config):
    # FIXME: the next line was added to avoid  'Task was destroyed but it is pending!' error
    tribler_config.api.http_enabled = True

    session = Session(tribler_config, [
        MasterKeyComponent.make_implementation(tribler_config, True),
        ReporterComponent.make_implementation(tribler_config, True),
        RESTComponent.make_implementation(tribler_config, True),
        UpgradeComponent.make_implementation(tribler_config, True),
        VersionCheckComponent.make_implementation(tribler_config, True),
    ])
    with session:
        comp = VersionCheckComponent.imp()
        assert comp.session is session
        assert isinstance(comp, VersionCheckComponent) and comp.__class__.__name__ == 'VersionCheckComponentImp'

        await session.start()
        assert comp.started.is_set()
        assert not comp.failed

        session.shutdown_event.set()
        await session.shutdown()
        assert comp.stopped


async def test_gigachannelmanagercomponent(loop, tribler_config):
    # FIXME: the next line was added to avoid  'Task was destroyed but it is pending!' error
    tribler_config.api.http_enabled = True

    tribler_config.libtorrent.enabled = True
    tribler_config.chant.enabled = True
    session = Session(tribler_config, [
        MasterKeyComponent.make_implementation(tribler_config, True),
        ReporterComponent.make_implementation(tribler_config, True),
        RESTComponent.make_implementation(tribler_config, True),
        UpgradeComponent.make_implementation(tribler_config, True),
        SocksServersComponent.make_implementation(tribler_config, True),
        LibtorrentComponent.make_implementation(tribler_config, True),
        MetadataStoreComponent.make_implementation(tribler_config, True),
        GigachannelManagerComponent.make_implementation(tribler_config, True),
    ])
    with session:
        comp = GigachannelManagerComponent.imp()
        assert comp.session is session
        assert isinstance(comp, GigachannelManagerComponent) and comp.__class__.__name__ == 'GigachannelManagerComponentImp'

        await session.start()
        assert comp.started.is_set()
        assert not comp.failed

        session.shutdown_event.set()
        await session.shutdown()
        assert comp.stopped
