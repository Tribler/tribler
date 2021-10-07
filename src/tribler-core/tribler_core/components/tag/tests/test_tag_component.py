import pytest

from tribler_core.components.base import Session
from tribler_core.components.ipv8.ipv8_component import Ipv8Component
from tribler_core.components.masterkey.masterkey_component import MasterKeyComponent
from tribler_core.components.restapi import RESTComponent
from tribler_core.components.tag.tag_component import TagComponent


# pylint: disable=protected-access


@pytest.mark.asyncio
async def test_tag_component(tribler_config):
    components = [MasterKeyComponent(), Ipv8Component(), RESTComponent(), TagComponent()]
    session = Session(tribler_config, components)
    with session:
        comp = TagComponent.instance()
        await session.start()

        assert comp.started_event.is_set() and not comp.failed
        assert comp.community

        await session.shutdown()
