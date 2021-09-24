from unittest.mock import patch

import pytest

from tribler_core.components.base import Session, SessionError
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
from tribler_core.restapi.rest_manager import RESTManager


# pylint: disable=protected-access

def test_session_context_manager(loop, tribler_config):
    session1 = Session(tribler_config, [])
    session2 = Session(tribler_config, [])
    session3 = Session(tribler_config, [])

    with pytest.raises(SessionError, match="Default session was not set"):
        Session.current()

    session1.set_as_default()
    assert Session.current() is session1

    with session2:
        assert Session.current() is session2
        with session3:
            assert Session.current() is session3
        assert Session.current() is session2
    assert Session.current() is session1

    Session.unset_default_session()

    with pytest.raises(SessionError, match="Default session was not set"):
        Session.current()


async def test_masterkey_component(tribler_config):
    session = Session(tribler_config, [MasterKeyComponent()])
    with session:
        comp = MasterKeyComponent.instance()
        await session.start()

        assert comp.keypair

        await session.shutdown()


async def test_bandwidth_accounting_component(tribler_config):
    components = [RESTComponent(), MasterKeyComponent(), Ipv8Component(), BandwidthAccountingComponent()]
    session = Session(tribler_config, components)
    with session:
        comp = BandwidthAccountingComponent.instance()
        with patch.object(RESTManager, 'get_endpoint'):
            await session.start()

            assert comp.community
            assert comp._rest_manager
            assert comp._ipv8

            await session.shutdown()


async def test_giga_channel_component(tribler_config):
    components = [MetadataStoreComponent(), RESTComponent(), MasterKeyComponent(), Ipv8Component(),
                  GigaChannelComponent()]
    session = Session(tribler_config, components)
    with session:
        comp = GigaChannelComponent.instance()
        with patch.object(RESTManager, 'get_endpoint'):
            await session.start()

            assert comp.community
            assert comp._rest_manager
            assert comp._ipv8

            await session.shutdown()


async def test_gigachannel_manager_component(tribler_config):
    components = [SocksServersComponent(), MasterKeyComponent(), RESTComponent(), MetadataStoreComponent(),
                  LibtorrentComponent(), GigachannelManagerComponent()]
    session = Session(tribler_config, components)
    with session:
        comp = GigachannelManagerComponent.instance()
        with patch.object(RESTManager, 'get_endpoint'):
            await session.start()

            assert comp.gigachannel_manager
            assert comp._rest_manager

            await session.shutdown()


async def test_ipv8_component(tribler_config):
    components = [MasterKeyComponent(), RESTComponent(), Ipv8Component()]
    session = Session(tribler_config, components)
    with session:
        comp = Ipv8Component.instance()
        with patch.object(RESTManager, 'get_endpoint'):
            await session.start()

            assert comp.ipv8
            assert comp.peer
            assert not comp.dht_discovery_community
            assert comp._task_manager
            assert comp._rest_manager
            assert not comp._peer_discovery_community

            await session.shutdown()


async def test_libtorrent_component(tribler_config):
    components = [RESTComponent(), MasterKeyComponent(), SocksServersComponent(), LibtorrentComponent()]
    session = Session(tribler_config, components)
    with session:
        comp = LibtorrentComponent.instance()
        with patch.object(RESTManager, 'get_endpoint'):
            await session.start()

            assert comp.download_manager
            assert comp._rest_manager

            await session.shutdown()


async def test_metadata_store_component(tribler_config):
    components = [MasterKeyComponent(), RESTComponent(), MetadataStoreComponent()]
    session = Session(tribler_config, components)
    with session:
        comp = MetadataStoreComponent.instance()
        with patch.object(RESTManager, 'get_endpoint'):
            await session.start()

            assert comp.mds
            assert comp._rest_manager

            await session.shutdown()


async def test_payout_component(tribler_config):
    components = [BandwidthAccountingComponent(), MasterKeyComponent(), RESTComponent(), Ipv8Component(),
                  PayoutComponent()]
    session = Session(tribler_config, components)
    with session:
        comp = PayoutComponent.instance()
        with patch.object(RESTManager, 'get_endpoint'):
            await session.start()

            assert comp.payout_manager

            await session.shutdown()


async def test_popularity_component(tribler_config):
    components = [SocksServersComponent(), LibtorrentComponent(), TorrentCheckerComponent(), MetadataStoreComponent(),
                  MasterKeyComponent(), RESTComponent(), Ipv8Component(), PopularityComponent()]
    session = Session(tribler_config, components)
    with session:
        comp = PopularityComponent.instance()
        with patch.object(RESTManager, 'get_endpoint'):
            await session.start()

            assert comp.community
            assert comp._ipv8

            await session.shutdown()


async def test_reporter_component(tribler_config):
    components = [ReporterComponent()]
    session = Session(tribler_config, components)
    with session:
        await session.start()
        await session.shutdown()


async def test_resource_monitor_component(tribler_config):
    components = [MasterKeyComponent(), RESTComponent(), ResourceMonitorComponent()]
    session = Session(tribler_config, components)
    with session:
        comp = ResourceMonitorComponent.instance()
        with patch.object(RESTManager, 'get_endpoint'):
            await session.start()

            assert comp.resource_monitor

            await session.shutdown()


async def test_REST_component(tribler_config):
    components = [MasterKeyComponent(), RESTComponent()]
    session = Session(tribler_config, components)
    with session:
        comp = RESTComponent.instance()
        with patch.object(RESTManager, 'get_endpoint'):
            await session.start()

            assert comp.rest_manager

            await session.shutdown()


async def test_socks_servers_component(tribler_config):
    components = [SocksServersComponent()]
    session = Session(tribler_config, components)
    with session:
        comp = SocksServersComponent.instance()
        with patch.object(RESTManager, 'get_endpoint'):
            await session.start()

            assert comp.socks_ports
            assert comp.socks_servers

            await session.shutdown()


async def test_torrent_checker_component(tribler_config):
    components = [SocksServersComponent(), LibtorrentComponent(), MasterKeyComponent(), RESTComponent(),
                  MetadataStoreComponent(), TorrentCheckerComponent()]
    session = Session(tribler_config, components)
    with session:
        comp = TorrentCheckerComponent.instance()
        with patch.object(RESTManager, 'get_endpoint'):
            await session.start()

            assert comp.torrent_checker
            assert comp._rest_manager

            await session.shutdown()


async def test_tunnels_component(tribler_config):
    components = [Ipv8Component(), MasterKeyComponent(), RESTComponent(), TunnelsComponent()]
    session = Session(tribler_config, components)
    with session:
        comp = TunnelsComponent.instance()
        with patch.object(RESTManager, 'get_endpoint'):
            await session.start()

            assert comp.community
            assert comp._ipv8

            await session.shutdown()


async def test_upgrade_component(tribler_config):
    components = [MasterKeyComponent(), RESTComponent(), UpgradeComponent()]
    session = Session(tribler_config, components)
    with session:
        comp = UpgradeComponent.instance()
        with patch.object(RESTManager, 'get_endpoint'):
            await session.start()

            assert comp.upgrader

            await session.shutdown()


async def test_version_check_component(tribler_config):
    components = [VersionCheckComponent()]
    session = Session(tribler_config, components)
    with session:
        comp = VersionCheckComponent.instance()
        with patch.object(RESTManager, 'get_endpoint'):
            await session.start()

            assert comp.version_check_manager

            await session.shutdown()


async def test_watch_folder_component(tribler_config):
    components = [MasterKeyComponent(), RESTComponent(), SocksServersComponent(), LibtorrentComponent(),
                  WatchFolderComponent()]
    session = Session(tribler_config, components)
    with session:
        comp = WatchFolderComponent.instance()
        with patch.object(RESTManager, 'get_endpoint'):
            await session.start()

            assert comp.watch_folder

            await session.shutdown()
