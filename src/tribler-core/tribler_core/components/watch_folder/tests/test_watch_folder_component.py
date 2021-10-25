import pytest

from tribler_core.components.base import Session
from tribler_core.components.key.key_component import KeyComponent
from tribler_core.components.libtorrent.libtorrent_component import LibtorrentComponent
from tribler_core.components.restapi.restapi_component import RESTComponent
from tribler_core.components.socks_servers.socks_servers_component import SocksServersComponent
from tribler_core.components.watch_folder.watch_folder_component import WatchFolderComponent

pytestmark = pytest.mark.asyncio


# pylint: disable=protected-access

async def test_watch_folder_component(tribler_config):
    components = [KeyComponent(), RESTComponent(), SocksServersComponent(), LibtorrentComponent(),
                  WatchFolderComponent()]
    session = Session(tribler_config, components)
    with session:
        await session.start()

        comp = WatchFolderComponent.instance()
        assert comp.started_event.is_set() and not comp.failed
        assert comp.watch_folder

        await session.shutdown()
