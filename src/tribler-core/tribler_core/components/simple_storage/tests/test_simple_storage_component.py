import pytest

from tribler_core.components.base import Session
from tribler_core.components.simple_storage.simple_storage_component import SimpleStorageComponent


# pylint: disable=protected-access


@pytest.mark.asyncio
async def test_simple_storage_component(tribler_config):
    # Test that component could be created without errors
    async with Session(tribler_config, [SimpleStorageComponent()]).start():
        comp = SimpleStorageComponent.instance()
        assert comp.started_event.is_set() and not comp.failed
