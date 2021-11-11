from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from tribler_common.reported_error import ReportedError

from tribler_core.components.base import Session
from tribler_core.components.key.key_component import KeyComponent
from tribler_core.components.reporter.exception_handler import CoreExceptionHandler
from tribler_core.components.restapi.rest.rest_manager import RESTManager
from tribler_core.components.restapi.restapi_component import RESTComponent

pytestmark = pytest.mark.asyncio


# pylint: disable=protected-access, not-callable


async def test_restful_component(tribler_config):
    components = [KeyComponent(), RESTComponent()]
    session = Session(tribler_config, components)
    with session:
        await session.start()

        comp = RESTComponent.instance()
        assert comp.started_event.is_set() and not comp.failed
        assert comp.rest_manager
        await session.shutdown()


@patch.object(RESTComponent, 'get_component', new=AsyncMock())
@patch.object(RESTManager, 'start', new=AsyncMock())
async def test_report_callback_set_up_correct():
    component = RESTComponent()
    component.session = MagicMock()

    component._core_exception_handler = CoreExceptionHandler()

    await component.run()

    # mock callbacks
    component._events_endpoint.on_tribler_exception = MagicMock()
    component._state_endpoint.on_tribler_exception = MagicMock()

    # try to call report_callback from core_exception_handler and assert
    # that corresponding methods in events_endpoint and state_endpoint have been called

    error = ReportedError(type='', text='text', event={})
    component._core_exception_handler.report_callback(error)
    component._events_endpoint.on_tribler_exception.assert_called_with(error)
    component._state_endpoint.on_tribler_exception.assert_called_with(error.text)
