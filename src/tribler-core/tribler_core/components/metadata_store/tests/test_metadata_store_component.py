from unittest.mock import patch

import pytest

from tribler_core.components.base import Session
from tribler_core.components.masterkey.masterkey_component import MasterKeyComponent
from tribler_core.components.metadata_store.metadata_store_component import MetadataStoreComponent
from tribler_core.components.restapi import RESTComponent
from tribler_core.restapi.rest_manager import RESTManager


# pylint: disable=protected-access

@pytest.mark.asyncio
async def test_metadata_store_component(tribler_config):
    components = [MasterKeyComponent(), RESTComponent(), MetadataStoreComponent()]
    session = Session(tribler_config, components)
    with session:
        comp = MetadataStoreComponent.instance()
        await session.start()

        assert comp.started_event.is_set() and not comp.failed
        assert comp.mds

        await session.shutdown()
