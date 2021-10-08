import pytest

from tribler_core.components.base import Session, SessionError
from tribler_core.components.ipv8.ipv8_component import Ipv8Component
from tribler_core.components.libtorrent.libtorrent_component import LibtorrentComponent
from tribler_core.components.masterkey.masterkey_component import MasterKeyComponent
from tribler_core.components.metadata_store.metadata_store_component import MetadataStoreComponent
from tribler_core.components.reporter import ReporterComponent
from tribler_core.components.restapi import RESTComponent
from tribler_core.components.socks_configurator import SocksServersComponent
from tribler_core.components.torrent_checker import TorrentCheckerComponent
from tribler_core.components.tunnels import TunnelsComponent
from tribler_core.components.upgrade import UpgradeComponent
from tribler_core.components.version_check import VersionCheckComponent
from tribler_core.components.watch_folder import WatchFolderComponent

pytestmark = pytest.mark.asyncio


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


async def test_reporter_component(tribler_config):
    components = [ReporterComponent()]
    session = Session(tribler_config, components)
    with session:
        await session.start()

        comp = ReporterComponent.instance()
        assert comp.started_event.is_set() and not comp.failed

        await session.shutdown()


async def test_REST_component(tribler_config):
    components = [MasterKeyComponent(), RESTComponent()]
    session = Session(tribler_config, components)
    with session:
        await session.start()

        comp = RESTComponent.instance()
        assert comp.started_event.is_set() and not comp.failed
        assert comp.rest_manager

        await session.shutdown()


async def test_socks_servers_component(tribler_config):
    components = [SocksServersComponent()]
    session = Session(tribler_config, components)
    with session:
        await session.start()

        comp = SocksServersComponent.instance()
        assert comp.started_event.is_set() and not comp.failed
        assert comp.socks_ports
        assert comp.socks_servers

        await session.shutdown()


async def test_torrent_checker_component(tribler_config):
    tribler_config.libtorrent.enabled = True
    tribler_config.chant.enabled = True
    components = [SocksServersComponent(), LibtorrentComponent(), MasterKeyComponent(), RESTComponent(),
                  MetadataStoreComponent(), TorrentCheckerComponent()]
    session = Session(tribler_config, components)
    with session:
        await session.start()

        comp = TorrentCheckerComponent.instance()
        assert comp.started_event.is_set() and not comp.failed
        assert comp.torrent_checker

        await session.shutdown()


async def test_tunnels_component(tribler_config):
    tribler_config.ipv8.enabled = True
    tribler_config.libtorrent.enabled = True
    tribler_config.chant.enabled = True
    components = [Ipv8Component(), MasterKeyComponent(), RESTComponent(), TunnelsComponent()]
    session = Session(tribler_config, components)
    with session:
        await session.start()

        comp = TunnelsComponent.instance()
        assert comp.started_event.is_set() and not comp.failed
        assert comp.community
        assert comp._ipv8_component

        await session.shutdown()


async def test_upgrade_component(tribler_config):
    components = [MasterKeyComponent(), RESTComponent(), UpgradeComponent()]
    session = Session(tribler_config, components)
    with session:
        await session.start()

        comp = UpgradeComponent.instance()
        assert comp.started_event.is_set() and not comp.failed
        assert comp.upgrader

        await session.shutdown()


async def test_version_check_component(tribler_config):
    components = [VersionCheckComponent()]
    session = Session(tribler_config, components)
    with session:
        await session.start()

        comp = VersionCheckComponent.instance()
        assert comp.started_event.is_set() and not comp.failed
        assert comp.version_check_manager

        await session.shutdown()


async def test_watch_folder_component(tribler_config):
    tribler_config.libtorrent.enabled = True
    tribler_config.chant.enabled = True
    components = [MasterKeyComponent(), RESTComponent(), SocksServersComponent(), LibtorrentComponent(),
                  WatchFolderComponent()]
    session = Session(tribler_config, components)
    with session:
        await session.start()

        comp = WatchFolderComponent.instance()
        assert comp.started_event.is_set() and not comp.failed
        assert comp.watch_folder

        await session.shutdown()
