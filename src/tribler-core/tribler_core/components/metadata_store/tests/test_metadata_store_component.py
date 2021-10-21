import pytest

from tribler_core.components.base import Session
from tribler_core.components.ipv8.ipv8_component import Ipv8Component
from tribler_core.components.key.key_component import KeyComponent
from tribler_core.components.metadata_store.metadata_store_component import MetadataStoreComponent
from tribler_core.components.restapi.restapi_component import RESTComponent
from tribler_core.components.tag.tag_component import TagComponent


# pylint: disable=protected-access

@pytest.mark.asyncio
async def test_metadata_store_component(tribler_config):
    components = [TagComponent(), Ipv8Component(), KeyComponent(), RESTComponent(), MetadataStoreComponent()]
    session = Session(tribler_config, components)
    with session:
        comp = MetadataStoreComponent.instance()
        await session.start()

        assert comp.started_event.is_set() and not comp.failed
        assert comp.mds

        await session.shutdown()
