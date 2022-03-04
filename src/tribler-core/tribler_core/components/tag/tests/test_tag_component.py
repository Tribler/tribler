import pytest

from tribler_core.components.base import Session
from tribler_core.components.ipv8.ipv8_component import Ipv8Component
from tribler_core.components.key.key_component import KeyComponent
from tribler_core.components.metadata_store.metadata_store_component import MetadataStoreComponent
from tribler_core.components.tag.tag_component import TagComponent

# pylint: disable=protected-access


@pytest.mark.asyncio
@pytest.mark.no_parallel
async def test_tag_component(tribler_config):
    components = [MetadataStoreComponent(), KeyComponent(), Ipv8Component(), TagComponent()]
    async with Session(tribler_config, components).start():
        comp = TagComponent.instance()
        assert comp.started_event.is_set() and not comp.failed
        assert comp.community
