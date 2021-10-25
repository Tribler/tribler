import pytest

from tribler_core.components.base import Session
from tribler_core.components.key.key_component import KeyComponent
from tribler_core.components.restapi.restapi_component import RESTComponent
from tribler_core.components.upgrade.upgrade_component import UpgradeComponent

pytestmark = pytest.mark.asyncio


# pylint: disable=protected-access

async def test_upgrade_component(tribler_config):
    components = [KeyComponent(), RESTComponent(), UpgradeComponent()]
    session = Session(tribler_config, components)
    with session:
        await session.start()

        comp = UpgradeComponent.instance()
        assert comp.started_event.is_set() and not comp.failed
        assert comp.upgrader

        await session.shutdown()
