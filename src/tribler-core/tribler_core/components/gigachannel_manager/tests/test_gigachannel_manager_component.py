from unittest.mock import patch

import pytest

from tribler_core.components.base import Session
from tribler_core.components.gigachannel_manager.gigachannel_manager_component import GigachannelManagerComponent
from tribler_core.components.libtorrent import LibtorrentComponent
from tribler_core.components.masterkey import MasterKeyComponent
from tribler_core.components.metadata_store.metadata_store_component import MetadataStoreComponent
from tribler_core.components.restapi import RESTComponent
from tribler_core.components.socks_configurator import SocksServersComponent
from tribler_core.restapi.rest_manager import RESTManager


# pylint: disable=protected-access

@pytest.mark.asyncio
async def test_gigachannel_manager_component(tribler_config):
    tribler_config.ipv8.enabled = True
    tribler_config.libtorrent.enabled = True
    tribler_config.chant.enabled = True
    components = [SocksServersComponent(), MasterKeyComponent(), RESTComponent(), MetadataStoreComponent(),
                  LibtorrentComponent(), GigachannelManagerComponent()]
    session = Session(tribler_config, components)
    with session:
        comp = GigachannelManagerComponent.instance()
        await session.start()

        assert comp.started.is_set() and not comp.failed
        assert comp.gigachannel_manager

        await session.shutdown()
