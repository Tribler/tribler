import pytest

from tribler_core.components.base import Session
from tribler_core.components.gigachannel_manager.gigachannel_manager_component import GigachannelManagerComponent
from tribler_core.components.ipv8.ipv8_component import Ipv8Component
from tribler_core.components.libtorrent.libtorrent_component import LibtorrentComponent
from tribler_core.components.key.key_component import KeyComponent
from tribler_core.components.metadata_store.metadata_store_component import MetadataStoreComponent
from tribler_core.components.restapi.restapi_component import RESTComponent
from tribler_core.components.socks_servers.socks_servers_component import SocksServersComponent
from tribler_core.components.tag.tag_component import TagComponent


# pylint: disable=protected-access


@pytest.mark.asyncio
async def test_gigachannel_manager_component(tribler_config):
    components = [Ipv8Component(), TagComponent(), SocksServersComponent(), KeyComponent(), RESTComponent(),
                  MetadataStoreComponent(),
                  LibtorrentComponent(), GigachannelManagerComponent()]
    session = Session(tribler_config, components)
    with session:
        comp = GigachannelManagerComponent.instance()
        await session.start()

        assert comp.started_event.is_set() and not comp.failed
        assert comp.gigachannel_manager

        await session.shutdown()
