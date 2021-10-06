import pytest

from tribler_core.components.base import Session
from tribler_core.components.libtorrent.libtorrent_component import LibtorrentComponent
from tribler_core.components.masterkey.masterkey_component import MasterKeyComponent
from tribler_core.components.restapi import RESTComponent
from tribler_core.components.socks_configurator import SocksServersComponent

pytestmark = pytest.mark.asyncio


# pylint: disable=protected-access

async def test_libtorrent_component(tribler_config):
    components = [RESTComponent(), MasterKeyComponent(), SocksServersComponent(), LibtorrentComponent()]
    session = Session(tribler_config, components)
    with session:
        await session.start()

        comp = LibtorrentComponent.instance()
        assert comp.started_event.is_set() and not comp.failed
        assert comp.download_manager

        await session.shutdown()
