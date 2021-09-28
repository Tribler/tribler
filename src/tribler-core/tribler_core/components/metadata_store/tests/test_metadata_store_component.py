from unittest.mock import patch

from tribler_core.components.base import Session
from tribler_core.components.masterkey import MasterKeyComponent
from tribler_core.components.metadata_store.metadata_store_component import MetadataStoreComponent
from tribler_core.components.restapi import RESTComponent
from tribler_core.restapi.rest_manager import RESTManager


# pylint: disable=protected-access

async def test_metadata_store_component(tribler_config):
    components = [MasterKeyComponent(), RESTComponent(), MetadataStoreComponent()]
    session = Session(tribler_config, components)
    with session:
        comp = MetadataStoreComponent.instance()
        with patch.object(RESTManager, 'get_endpoint'):
            await session.start()

            assert comp.mds
            assert comp._rest_manager

            await session.shutdown()
