import pytest

from tribler_core.components.base import Session
from tribler_core.components.version_check.version_check_component import VersionCheckComponent

pytestmark = pytest.mark.asyncio


# pylint: disable=protected-access

async def test_version_check_component(tribler_config):
    components = [VersionCheckComponent()]
    session = Session(tribler_config, components)
    with session:
        await session.start()

        comp = VersionCheckComponent.instance()
        assert comp.started_event.is_set() and not comp.failed
        assert comp.version_check_manager

        await session.shutdown()
