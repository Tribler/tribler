import pytest

from tribler_core.components.base import Session, SessionError
from tribler_core.components.key.key_component import KeyComponent
from tribler_core.components.libtorrent.libtorrent_component import LibtorrentComponent
from tribler_core.components.restapi.restapi_component import RESTComponent
from tribler_core.components.socks_servers.socks_servers_component import SocksServersComponent
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
    components = [KeyComponent(), RESTComponent(), SocksServersComponent(), LibtorrentComponent(),
                  WatchFolderComponent()]
    session = Session(tribler_config, components)
    with session:
        await session.start()

        comp = WatchFolderComponent.instance()
        assert comp.started_event.is_set() and not comp.failed
        assert comp.watch_folder

        await session.shutdown()
