import pytest

from tribler.core.components.base import Session
from tribler.core.components.ipv8.ipv8_component import Ipv8Component
from tribler.core.components.key.key_component import KeyComponent
from tribler.core.components.libtorrent.libtorrent_component import LibtorrentComponent
from tribler.core.components.metadata_store.metadata_store_component import MetadataStoreComponent
from tribler.core.components.popularity.popularity_component import PopularityComponent
from tribler.core.components.socks_servers.socks_servers_component import SocksServersComponent
from tribler.core.components.tag.tag_component import TagComponent
from tribler.core.components.torrent_checker.torrent_checker_component import TorrentCheckerComponent

# pylint: disable=protected-access


async def test_popularity_component(tribler_config):
    components = [SocksServersComponent(), LibtorrentComponent(), TorrentCheckerComponent(), TagComponent(),
                  MetadataStoreComponent(), KeyComponent(), Ipv8Component(), PopularityComponent()]
    async with Session(tribler_config, components).start():
        comp = PopularityComponent.instance()
        assert comp.community
        assert comp._ipv8_component
