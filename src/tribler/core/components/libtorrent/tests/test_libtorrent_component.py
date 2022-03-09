import pytest

from tribler_core.components.base import Session
from tribler_core.components.key.key_component import KeyComponent
from tribler_core.components.libtorrent.libtorrent_component import LibtorrentComponent
from tribler_core.components.socks_servers.socks_servers_component import SocksServersComponent


# pylint: disable=protected-access
@pytest.mark.asyncio
@pytest.mark.no_parallel
async def test_libtorrent_component(tribler_config):
    components = [KeyComponent(), SocksServersComponent(), LibtorrentComponent()]
    async with Session(tribler_config, components).start():
        comp = LibtorrentComponent.instance()
        assert comp.started_event.is_set() and not comp.failed
        assert comp.download_manager
