from tribler.core.components.gigachannel_manager.gigachannel_manager_component import GigachannelManagerComponent
from tribler.core.components.ipv8.ipv8_component import Ipv8Component
from tribler.core.components.key.key_component import KeyComponent
from tribler.core.components.knowledge.knowledge_component import KnowledgeComponent
from tribler.core.components.libtorrent.libtorrent_component import LibtorrentComponent
from tribler.core.components.metadata_store.metadata_store_component import MetadataStoreComponent
from tribler.core.components.session import Session
from tribler.core.components.socks_servers.socks_servers_component import SocksServersComponent

# pylint: disable=protected-access


async def test_gigachannel_manager_component(tribler_config):
    components = [Ipv8Component(), KnowledgeComponent(), SocksServersComponent(), KeyComponent(),
                  MetadataStoreComponent(),
                  LibtorrentComponent(), GigachannelManagerComponent()]
    async with Session(tribler_config, components) as session:
        comp = session.get_instance(GigachannelManagerComponent)
        assert comp.started_event.is_set()
        assert not comp.failed
        assert comp.gigachannel_manager
