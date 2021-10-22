import pytest

from tribler_core.components.base import Session
from tribler_core.components.key.key_component import KeyComponent
from tribler_core.components.restapi.restapi_component import RESTComponent

pytestmark = pytest.mark.asyncio


# pylint: disable=protected-access
async def test_restful_component(tribler_config):
    components = [KeyComponent(), RESTComponent()]
    session = Session(tribler_config, components)
    with session:
        await session.start()

        comp = RESTComponent.instance()
        assert comp.started_event.is_set() and not comp.failed
        assert comp.rest_manager

        await session.shutdown()
