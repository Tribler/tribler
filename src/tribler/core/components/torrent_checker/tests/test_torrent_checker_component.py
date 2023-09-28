from tribler.core.components.database.database_component import DatabaseComponent
from tribler.core.components.ipv8.ipv8_component import Ipv8Component
from tribler.core.components.key.key_component import KeyComponent
from tribler.core.components.knowledge.knowledge_component import KnowledgeComponent
from tribler.core.components.libtorrent.libtorrent_component import LibtorrentComponent
from tribler.core.components.metadata_store.metadata_store_component import MetadataStoreComponent
from tribler.core.components.session import Session
from tribler.core.components.socks_servers.socks_servers_component import SocksServersComponent
from tribler.core.components.torrent_checker.torrent_checker_component import TorrentCheckerComponent


# pylint: disable=protected-access
async def test_torrent_checker_component(tribler_config):
    components = [DatabaseComponent(), SocksServersComponent(), LibtorrentComponent(), KeyComponent(),
                  Ipv8Component(), KnowledgeComponent(), MetadataStoreComponent(), TorrentCheckerComponent()]
    async with Session(tribler_config, components) as session:
        comp = session.get_instance(TorrentCheckerComponent)
        assert comp.started_event.is_set() and not comp.failed
        assert comp.torrent_checker
