from unittest.mock import patch

from tribler_core.components.base import Session
from tribler_core.components.gigachannel.gigachannel_component import GigaChannelComponent
from tribler_core.components.ipv8 import Ipv8Component
from tribler_core.components.masterkey import MasterKeyComponent
from tribler_core.components.metadata_store.metadata_store_component import MetadataStoreComponent
from tribler_core.components.restapi import RESTComponent
from tribler_core.restapi.rest_manager import RESTManager


# pylint: disable=protected-access


async def test_giga_channel_component(tribler_config):
    tribler_config.ipv8.enabled = True
    tribler_config.libtorrent.enabled = True
    tribler_config.chant.enabled = True
    components = [MetadataStoreComponent(), RESTComponent(), MasterKeyComponent(), Ipv8Component(),
                  GigaChannelComponent()]
    session = Session(tribler_config, components)
    with session:
        await session.start()

        comp = GigaChannelComponent.instance()
        assert comp.started.is_set() and not comp.failed
        assert comp.community
        assert comp._rest_manager
        assert comp._ipv8

        await session.shutdown()
